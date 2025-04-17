from typing import Dict
from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.print.printer import Printer

from bloqade import stim
from bloqade.squin import op, wire, qubit
from bloqade.analysis.address import Address, AddressWire, AddressQubit, AddressTuple
from bloqade.squin.analysis.nsites import Sites

# Probably best to move these attributes to a
# separate file? Keep here for now
# to get things working first


@wire.dialect.register
@dataclass
class AddressAttribute(ir.Attribute):

    name = "Address"
    address: Address

    def __hash__(self) -> int:
        return hash(self.address)

    def print_impl(self, printer: Printer) -> None:
        # Can return to implementing this later
        printer.print(self.address)


@op.dialect.register
@dataclass
class SitesAttribute(ir.Attribute):

    name = "Sites"
    sites: Sites

    def __hash__(self) -> int:
        return hash(self.sites)

    def print_impl(self, printer: Printer) -> None:
        # Can return to implementing this later
        printer.print(self.sites)


@dataclass
class WrapSquinAnalysis(RewriteRule):

    address_analysis: Dict[ir.SSAValue, Address]
    op_site_analysis: Dict[ir.SSAValue, Sites]

    def wrap(self, value: ir.SSAValue) -> bool:
        address_analysis_result = self.address_analysis[value]
        op_site_analysis_result = self.op_site_analysis[value]

        if value.hints.get("address") and value.hints.get("sites"):
            return False
        else:
            value.hints["address"] = AddressAttribute(address_analysis_result)
            value.hints["sites"] = SitesAttribute(op_site_analysis_result)

        return True

    def rewrite_Block(self, node: ir.Block) -> RewriteResult:
        has_done_something = False
        for arg in node.args:
            if self.wrap(arg):
                has_done_something = True
        return RewriteResult(has_done_something=has_done_something)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        has_done_something = False
        for result in node.results:
            if self.wrap(result):
                has_done_something = True
        return RewriteResult(has_done_something=has_done_something)


@dataclass
class _SquinToStim(RewriteRule):

    def get_address_attr(self, value: ir.SSAValue) -> AddressAttribute:

        try:
            address_attr = value.hints["address"]
            assert isinstance(address_attr, AddressAttribute)
            return address_attr
        except KeyError:
            raise KeyError(f"The address analysis hint for {value} does not exist")

    def get_sites_attr(self, value: ir.SSAValue):
        try:
            return value.hints["sites"]
        except KeyError:
            raise KeyError(f"The sites analysis hint for {value} does not exist")

    # Go from (most) squin 1Q Ops to stim Ops
    ## X, Y, Z, H, S, (no T!)
    def get_stim_1q_gate(self, squin_op: op.stmts.Operator):
        match squin_op:
            case op.stmts.X():
                return stim.gate.X
            case op.stmts.Y():
                return stim.gate.Y
            case op.stmts.Z():
                return stim.gate.Z
            case op.stmts.H():
                return stim.gate.H
            case op.stmts.S():
                return stim.gate.S
            case op.stmts.Identity():  # enforce sites defined = num wires in
                return stim.gate.Identity
            case _:
                raise NotImplementedError(
                    f"The squin operator {squin_op} is not supported in the stim dialect"
                )

    def insert_qubit_idx_from_address(
        self, address: AddressAttribute, stmt_to_insert_before: ir.Statement
    ) -> tuple[ir.SSAValue, ...]:

        address_data = address.address

        qubit_idx_ssas = []

        if isinstance(address_data, AddressTuple):
            for address_qubit in address_data.data:

                # ensure that the stuff in the AddressTuple should be AddressQubit
                # could handle AddressWires as well but don't see the need for that right now
                if not isinstance(address_qubit, AddressQubit):
                    raise ValueError(
                        "Unsupported Address type detected inside AddressTuple, must be AddressQubit"
                    )
                qubit_idx = address_qubit.data
                qubit_idx_stmt = py.Constant(qubit_idx)
                qubit_idx_stmt.insert_before(stmt_to_insert_before)
                qubit_idx_ssas.append(qubit_idx_stmt.result)
        elif isinstance(address_data, AddressWire):
            address_qubit = address_data.origin_qubit
            qubit_idx = address_qubit.data
            qubit_idx_stmt = py.Constant(qubit_idx)
            qubit_idx_stmt.insert_before(stmt_to_insert_before)
            qubit_idx_ssas.append(qubit_idx_stmt.result)
        else:
            NotImplementedError(
                "qubit idx extraction and insertion only support for AddressTuple[AddressQubit] and AddressWire instances"
            )

        return tuple(qubit_idx_ssas)

    def insert_qubit_idx_from_wire_ssa(
        self, wire_ssas: tuple[ir.SSAValue, ...], stmt_to_insert_before: ir.Statement
    ) -> tuple[ir.SSAValue, ...]:
        qubit_idx_ssas = []
        for wire_ssa in wire_ssas:
            address_attribute = self.get_address_attr(wire_ssa)  # get AddressWire
            # get parent qubit idx
            wire_address = address_attribute.address
            assert isinstance(wire_address, AddressWire)
            qubit_idx = wire_address.origin_qubit.data
            qubit_idx_stmt = py.Constant(qubit_idx)
            # accumulate all qubit idx SSA to instantiate stim gate stmt
            qubit_idx_ssas.append(qubit_idx_stmt.result)
            qubit_idx_stmt.insert_before(stmt_to_insert_before)

        return tuple(qubit_idx_ssas)

    # get the qubit indices from the Apply statement argument
    # wires/qubits

    def insert_qubit_idx_after_apply(
        self, apply_stmt: wire.Apply | qubit.Apply
    ) -> tuple[ir.SSAValue, ...]:

        if isinstance(apply_stmt, qubit.Apply):
            qubits = apply_stmt.qubits
            address_attribute: AddressAttribute = self.get_address_attr(qubits)
            # Should get an AddressTuple out of the address stored in attribute
            return self.insert_qubit_idx_from_address(
                address=address_attribute, stmt_to_insert_before=apply_stmt
            )
        elif isinstance(apply_stmt, wire.Apply):
            wire_ssas = apply_stmt.inputs
            return self.insert_qubit_idx_from_wire_ssa(
                wire_ssas=wire_ssas, stmt_to_insert_before=apply_stmt
            )
        else:
            raise TypeError(
                "unsupported statement detected, only wire.Apply and qubit.Apply statements are supported by this method"
            )

    # might be worth attempting multiple dispatch like qasm2 rewrites
    # for Glob and Parallel to UOp
    # The problem is I'd have to introduce names for all the statements
    # as a ClassVar str. Maybe hold off for now.

    # Don't translate constants to Stim Aux Constants just yet,
    # The Stim operations don't even rely on those particular
    # constants, seems to be more for lowering from Python AST

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case wire.Apply() | qubit.Apply():
                return self.rewrite_Apply(node)
            case wire.Wrap():
                return self.rewrite_Wrap(node)
            case wire.Measure() | qubit.Measure():
                return self.rewrite_Measure(node)
            case wire.Reset() | qubit.Reset():
                return self.rewrite_Reset(node)
            case wire.MeasureAndReset() | qubit.MeasureAndReset():
                return self.rewrite_MeasureAndReset(node)
            case _:
                return RewriteResult()

        return RewriteResult()

    def rewrite_Wrap(self, wrap_stmt: wire.Wrap) -> RewriteResult:

        # get the wire going into the statement
        wire_ssa = wrap_stmt.wire
        # remove the wrap statement altogether, then the wire that went into it
        wrap_stmt.delete()
        wire_ssa.delete()

        # do NOT want to delete the qubit SSA! Leave that alone!
        return RewriteResult(has_done_something=True)

    def rewrite_Apply(self, apply_stmt: qubit.Apply | wire.Apply) -> RewriteResult:

        # this is an SSAValue, need it to be the actual operator
        applied_op = apply_stmt.operator.owner
        assert isinstance(applied_op, op.stmts.Operator)

        if isinstance(applied_op, op.stmts.Control):
            return self.rewrite_Control(apply_stmt)

        # need to handle Control through separate means
        # but we can handle X, Y, Z, H, and S here just fine
        stim_1q_op = self.get_stim_1q_gate(applied_op)

        # wire.Apply -> tuple of SSA -> AddressTuple
        # qubit.Apply -> list of qubits ->  AddressTuple
        ## Both cases the statements follow the Stim semantics of
        ## 1QGate a b c d ....

        if isinstance(apply_stmt, qubit.Apply):
            address_attr = self.get_address_attr(apply_stmt.qubits)
            qubit_idx_ssas = self.insert_qubit_idx_from_address(
                address=address_attr, stmt_to_insert_before=apply_stmt
            )
        elif isinstance(apply_stmt, wire.Apply):
            qubit_idx_ssas = self.insert_qubit_idx_from_wire_ssa(
                wire_ssas=apply_stmt.inputs, stmt_to_insert_before=apply_stmt
            )
        else:
            raise TypeError(
                "Unsupported statement detected, only qubit.Apply and wire.Apply are permitted"
            )

        stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas))
        stim_1q_stmt.insert_before(apply_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_Control(
        self, apply_stmt_ctrl: qubit.Apply | wire.Apply
    ) -> RewriteResult:
        # stim only supports CX, CY, CZ so we have to check the
        # operator of Apply is a Control gate, enforce it's only asking for 1 control qubit,
        # and that the target of the control is X, Y, Z in squin

        ctrl_op = apply_stmt_ctrl.operator.owner
        assert isinstance(ctrl_op, op.stmts.Control)

        # enforce that n_controls is 1

        ctrl_op_target_gate = ctrl_op.op.owner
        assert isinstance(ctrl_op_target_gate, op.stmts.Operator)

        # should enforce that this is some multiple of 2
        qubit_idx_ssas = self.insert_qubit_idx_after_apply(apply_stmt=apply_stmt_ctrl)
        # according to stim, final result can be:
        # CX 1 2 3 4 -> CX(1, targ=2), CX(3, targ=4)
        target_qubits = []
        ctrl_qubits = []
        # definitely a better way to do this but
        # can't think of it right now
        for i in range(len(qubit_idx_ssas)):
            if (i % 2) == 0:
                ctrl_qubits.append(qubit_idx_ssas[i])
            else:
                target_qubits.append(qubit_idx_ssas[i])

        target_qubits = tuple(target_qubits)
        ctrl_qubits = tuple(ctrl_qubits)

        match ctrl_op_target_gate:
            case op.stmts.X():
                stim_stmt = stim.CX(controls=ctrl_qubits, targets=target_qubits)
            case op.stmts.Y():
                stim_stmt = stim.CY(controls=ctrl_qubits, targets=target_qubits)
            case op.stmts.Z():
                stim_stmt = stim.CZ(controls=ctrl_qubits, targets=target_qubits)
            case _:
                raise NotImplementedError(
                    "Control gates beyond CX, CY, and CZ are not supported"
                )

        stim_stmt.insert_before(apply_stmt_ctrl)

        return RewriteResult(has_done_something=True)

    def rewrite_Measure(
        self, measure_stmt: qubit.Measure | wire.Measure
    ) -> RewriteResult:

        if isinstance(measure_stmt, qubit.Measure):
            qubit_ilist_ssa = measure_stmt.qubits
            address_attr = self.get_address_attr(qubit_ilist_ssa)

        elif isinstance(measure_stmt, wire.Measure):
            # Wire Terminator, should kill the existence of
            # the wire here so DCE can sweep up the rest like with rewriting wrap
            wire_ssa = measure_stmt.wire
            address_attr = self.get_address_attr(wire_ssa)

            # DCE can't remove the old measure_stmt for both wire and qubit versions
            # because of the fact it has a result that can be depended on by other statements
            # whereas Stim Measure has no such notion

        else:
            raise TypeError(
                "unsupported Statement, only qubit.Measure and wire.Measure are supported"
            )

        qubit_idx_ssas = self.insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=measure_stmt
        )

        prob_noise_stmt = py.constant.Constant(0.0)
        stim_measure_stmt = stim.collapse.MZ(
            p=prob_noise_stmt.result,
            targets=qubit_idx_ssas,
        )
        prob_noise_stmt.insert_before(measure_stmt)
        stim_measure_stmt.insert_before(measure_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_Reset(self, reset_stmt: qubit.Reset | wire.Reset) -> RewriteResult:
        """
        qubit.Reset(ilist of qubits) -> nothing
        # safe to delete the statement afterwards, no depending results
        # DCE could probably do this automatically?

        wire.Reset(single wire) -> new wire
        # DO NOT DELETE

        # assume RZ, but could extend to RY and RX later
        Stim RZ(targets = tuple[int of SSAVals])
        """

        if isinstance(reset_stmt, qubit.Reset):
            qubit_ilist_ssa = reset_stmt.qubits
            # qubits are in an ilist which makes up an AddressTuple
            address_attr = self.get_address_attr(qubit_ilist_ssa)
            qubit_idx_ssas = self.insert_qubit_idx_from_address(
                address=address_attr, stmt_to_insert_before=reset_stmt
            )
        elif isinstance(reset_stmt, wire.Reset):
            address_attr = self.get_address_attr(reset_stmt.wire)
            qubit_idx_ssas = self.insert_qubit_idx_from_address(
                address=address_attr, stmt_to_insert_before=reset_stmt
            )
        else:
            raise TypeError(
                "unsupported statement, only qubit.Reset and wire.Reset are supported"
            )

        stim_rz_stmt = stim.collapse.stmts.RZ(targets=qubit_idx_ssas)
        stim_rz_stmt.insert_before(reset_stmt)
        reset_stmt.delete()

        return RewriteResult(has_done_something=True)

    def rewrite_MeasureAndReset(
        self, meas_and_reset_stmt: qubit.MeasureAndReset | wire.MeasureAndReset
    ):
        """
        qubit.MeasureAndReset(qubits) -> result
        Could be translated (roughly equivalent) to

        stim.MZ(tuple[SSAvals for ints])
        stim.RZ(tuple[SSAvals for ints])

        Stim does have MRZ, might be more reflective of what we want/
        lines up the semantics better

        """

        if isinstance(meas_and_reset_stmt, qubit.MeasureAndReset):

            address_attr = self.get_address_attr(meas_and_reset_stmt.qubits)
            qubit_idx_ssas = self.insert_qubit_idx_from_address(
                address=address_attr, stmt_to_insert_before=meas_and_reset_stmt
            )

        elif isinstance(meas_and_reset_stmt, wire.MeasureAndReset):
            address_attr = self.get_address_attr(meas_and_reset_stmt.wire)
            qubit_idx_ssas = self.insert_qubit_idx_from_address(
                address_attr, stmt_to_insert_before=meas_and_reset_stmt
            )

        else:
            raise TypeError(
                "Unsupported statement detected, only qubit.MeasureAndReset and wire.MeasureAndReset are supported"
            )

        error_p_stmt = py.Constant(0.0)
        stim_mz_stmt = stim.collapse.MZ(targets=qubit_idx_ssas, p=error_p_stmt.result)
        stim_rz_stmt = stim.collapse.RZ(
            targets=qubit_idx_ssas,
        )
        error_p_stmt.insert_before(meas_and_reset_stmt)
        stim_mz_stmt.insert_before(meas_and_reset_stmt)
        stim_rz_stmt.insert_before(meas_and_reset_stmt)

        return RewriteResult(has_done_something=True)
