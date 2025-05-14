from typing import Dict, cast
from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.print.printer import Printer

from bloqade import stim
from bloqade.squin import op, wire, qubit
from bloqade.analysis.address import Address, AddressWire, AddressQubit, AddressTuple
from bloqade.squin.analysis.nsites import Sites, NumberSites

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
            sites_attr = value.hints["sites"]
            assert isinstance(sites_attr, SitesAttribute)
            return sites_attr
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
            case op.stmts.Identity():
                return stim.gate.Identity
            case _:
                raise NotImplementedError(
                    f"The squin operator {squin_op} is not supported in the stim dialect"
                )

    def insert_qubit_idx_from_address(
        self, address: AddressAttribute, stmt_to_insert_before: ir.Statement
    ) -> tuple[ir.SSAValue, ...]:
        """
        Given an AddressAttribute which wraps the result of address analysis for a statement,
        extract the qubit indices from the address type and insert them into the SSA form.

        Currently supports AddressTuple[AddressQubit] and AddressWire types.
        """

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

    def verify_num_sites(
        self, stmt: wire.Apply | qubit.Apply | wire.Broadcast | qubit.Broadcast
    ):
        """
        Ensure for Apply statements that the number of qubits/wires strictly matches the number of sites
        supported by the operator, and for Broadcast statements that the number of qubits/wires
        is a multiple of the number of sites supported by the operator.
        """

        # Determine the number of sites targeted
        ## wire.Apply and wire.Broadcast takes a standard python tuple of SSAValues,
        ## qubit.Apply and qubit.Broadcast takes an AddressTuple of AddressQubits
        ## and need some extra logic to extract the number of sites targeted
        if isinstance(stmt, (wire.Apply, wire.Broadcast)):
            num_sites_targeted = len(stmt.inputs)
        elif isinstance(stmt, (qubit.Apply, qubit.Broadcast)):
            address_attr = self.get_address_attr(stmt.qubits)
            address_tuple = address_attr.address
            assert isinstance(address_tuple, AddressTuple)
            num_sites_targeted = len(address_tuple.data)
        else:
            raise TypeError(
                "Number of sites verification can only occur on Apply or Broadcast statements"
            )

        # Get the operator and its supported number of sites
        op_ssa = stmt.operator
        op_stmt = op_ssa.owner
        cast(ir.Statement, op_stmt)

        sites_attr = self.get_sites_attr(op_ssa)
        sites_type = sites_attr.sites
        assert isinstance(sites_type, NumberSites)
        num_sites_supported = sites_type.sites

        # Perform the verification
        if isinstance(stmt, (wire.Broadcast, qubit.Broadcast)):
            if num_sites_targeted % num_sites_supported != 0:
                raise ValueError(
                    "Number of qubits/wires to broadcast to must be a multiple of the number of sites supported by the operator"
                )
        elif isinstance(stmt, (wire.Apply, qubit.Apply)):
            if num_sites_targeted != num_sites_supported:
                raise ValueError(
                    "Number of qubits/wires to apply to must match the number of sites supported by the operator"
                )

        return None

    # Don't translate constants to Stim Aux Constants just yet,
    # The Stim operations don't even rely on those particular
    # constants, seems to be more for lowering from Python AST

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case wire.Apply() | qubit.Apply() | wire.Broadcast() | qubit.Broadcast():
                self.verify_num_sites(node)
                return self.rewrite_Apply_and_Broadcast(node)
            case wire.Wrap():
                return self.rewrite_Wrap(node)
            case wire.Measure() | qubit.MeasureQubit() | qubit.MeasureQubitList():
                return self.rewrite_Measure(node)
            case wire.Reset() | qubit.Reset():
                return self.rewrite_Reset(node)
            case wire.MeasureAndReset() | qubit.MeasureAndReset():
                return self.rewrite_MeasureAndReset(node)
            case _:
                return RewriteResult()

    def rewrite_Wrap(self, wrap_stmt: wire.Wrap) -> RewriteResult:

        # get the wire going into the statement
        wire_ssa = wrap_stmt.wire
        # remove the wrap statement altogether, then the wire that went into it
        wrap_stmt.delete()
        wire_ssa.delete()

        # do NOT want to delete the qubit SSA! Leave that alone!
        return RewriteResult(has_done_something=True)

    def rewrite_Apply_and_Broadcast(
        self, apply_stmt: qubit.Apply | wire.Apply | qubit.Broadcast | wire.Broadcast
    ) -> RewriteResult:
        # this is an SSAValue, need it to be the actual operator
        applied_op = apply_stmt.operator.owner
        assert isinstance(applied_op, op.stmts.Operator)

        if isinstance(applied_op, op.stmts.Control):
            return self.rewrite_Control(apply_stmt)

        # need to handle Control through separate means
        # but we can handle X, Y, Z, H, and S here just fine
        stim_1q_op = self.get_stim_1q_gate(applied_op)

        if isinstance(apply_stmt, (qubit.Apply, qubit.Broadcast)):
            address_attr = self.get_address_attr(apply_stmt.qubits)
            qubit_idx_ssas = self.insert_qubit_idx_from_address(
                address=address_attr, stmt_to_insert_before=apply_stmt
            )
        elif isinstance(apply_stmt, (wire.Apply, wire.Broadcast)):
            qubit_idx_ssas = self.insert_qubit_idx_from_wire_ssa(
                wire_ssas=apply_stmt.inputs, stmt_to_insert_before=apply_stmt
            )
        else:
            raise TypeError(
                "Unsupported statement detected, only Apply and Broadcast statements are permitted"
            )

        stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas))
        stim_1q_stmt.insert_before(apply_stmt)

        # Could I safely delete the apply statements?
        # If it's a qubit.Apply or qubit.Broadcast, yes, because it doesn't return anything
        # If it's a wire.Apply or wire.Broadcast, no, because the `results` of that Apply/Broadcast get used later on
        if isinstance(apply_stmt, (qubit.Apply, qubit.Broadcast)):
            apply_stmt.delete()

        return RewriteResult(has_done_something=True)

    def rewrite_Control(
        self,
        stmt_with_ctrl: qubit.Apply | wire.Apply | qubit.Broadcast | wire.Broadcast,
    ) -> RewriteResult:
        """
        Handle control gates for Apply and Broadcast statements.
        """
        ctrl_op = stmt_with_ctrl.operator.owner
        assert isinstance(ctrl_op, op.stmts.Control)

        ctrl_op_target_gate = ctrl_op.op.owner
        assert isinstance(ctrl_op_target_gate, op.stmts.Operator)

        qubit_idx_ssas = self.insert_qubit_idx_after_apply(stmt=stmt_with_ctrl)

        # Separate control and target qubits
        target_qubits = []
        ctrl_qubits = []
        for i in range(len(qubit_idx_ssas)):
            if (i % 2) == 0:
                ctrl_qubits.append(qubit_idx_ssas[i])
            else:
                target_qubits.append(qubit_idx_ssas[i])

        target_qubits = tuple(target_qubits)
        ctrl_qubits = tuple(ctrl_qubits)

        # Handle supported gates
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

        stim_stmt.insert_before(stmt_with_ctrl)

        # Delete the original statement if it's a qubit.Apply or qubit.Broadcast
        if isinstance(stmt_with_ctrl, (qubit.Apply, qubit.Broadcast)):
            stmt_with_ctrl.delete()

        return RewriteResult(has_done_something=True)

    def insert_qubit_idx_after_apply(
        self, stmt: wire.Apply | qubit.Apply | wire.Broadcast | qubit.Broadcast
    ) -> tuple[ir.SSAValue, ...]:
        """
        Extract qubit indices from Apply or Broadcast statements.
        """
        if isinstance(stmt, (qubit.Apply, qubit.Broadcast)):
            qubits = stmt.qubits
            address_attribute: AddressAttribute = self.get_address_attr(qubits)
            return self.insert_qubit_idx_from_address(
                address=address_attribute, stmt_to_insert_before=stmt
            )
        elif isinstance(stmt, (wire.Apply, wire.Broadcast)):
            wire_ssas = stmt.inputs
            return self.insert_qubit_idx_from_wire_ssa(
                wire_ssas=wire_ssas, stmt_to_insert_before=stmt
            )
        else:
            raise TypeError(
                "Unsupported statement detected, only Apply and Broadcast statements are supported by this method"
            )

    # qubit.Measure no longer exists, need to handle
    # qubit.MeasureQubit and MeasureQubitList
    def rewrite_Measure(
        self, measure_stmt: wire.Measure | qubit.MeasureQubit | qubit.MeasureQubitList
    ) -> RewriteResult:

        match measure_stmt:
            case qubit.MeasureQubit():
                qubit_ilist_ssa = measure_stmt.qubit
                address_attr = self.get_address_attr(qubit_ilist_ssa)
            case qubit.MeasureQubitList():
                qubit_ssa = measure_stmt.qubits
                address_attr = self.get_address_attr(qubit_ssa)
            case wire.Measure():
                wire_ssa = measure_stmt.wire
                address_attr = self.get_address_attr(wire_ssa)
            case _:
                raise TypeError(
                    "Unsupported Statement, only qubit.MeasureQubit, qubit.MeasureQubitList, and wire.Measure are supported"
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
