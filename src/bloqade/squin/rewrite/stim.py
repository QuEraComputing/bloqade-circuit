from typing import Dict
from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.print.printer import Printer

from bloqade import stim
from bloqade.squin import op, wire, qubit
from bloqade.analysis.address import Address, AddressWire, AddressTuple
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

    def get_address(self, value: ir.SSAValue):
        try:
            return value.hints["address"]
        except KeyError:
            raise KeyError(f"The address analysis hint for {value} does not exist")

    def get_sites(self, value: ir.SSAValue):
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

    # get the qubit indices from the Apply statement argument
    # wires/qubits
    def insert_qubit_idx_ssa(
        self, apply_stmt: wire.Apply | qubit.Apply
    ) -> tuple[ir.SSAValue, ...]:

        if isinstance(apply_stmt, qubit.Apply):
            qubits = apply_stmt.qubits
            address_attribute: AddressAttribute = self.get_address(qubits)
            # Should get an AddressTuple out of the address stored in attribute
            address_tuple = address_attribute.address
            qubit_idx_ssas: list[ir.SSAValue] = []
            for address_qubit in address_tuple.data:
                qubit_idx = address_qubit.data
                qubit_idx_stmt = py.Constant(qubit_idx)
                qubit_idx_stmt.insert_before(apply_stmt)
                qubit_idx_ssas.append(qubit_idx_stmt.result)

            return tuple(qubit_idx_ssas)

        elif isinstance(apply_stmt, wire.Apply):
            wire_ssas = apply_stmt.inputs
            qubit_idx_ssas: list[ir.SSAValue] = []
            for wire_ssa in wire_ssas:
                address_attribute = self.get_address(wire_ssa)
                # get parent qubit idx
                wire_address = address_attribute.address
                qubit_idx = wire_address.origin_qubit.data
                qubit_idx_stmt = py.Constant(qubit_idx)
                # accumulate all qubit idx SSA to instantiate stim gate stmt
                qubit_idx_ssas.append(qubit_idx_stmt.result)
                qubit_idx_stmt.insert_before(apply_stmt)

            return tuple(qubit_idx_ssas)

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

        if isinstance(applied_op, op.stmts.Control):
            return self.rewrite_Control(apply_stmt)

        # need to handle Control through separate means
        # but we can handle X, Y, Z, H, and S here just fine
        stim_1q_op = self.get_stim_1q_gate(applied_op)

        qubit_idx_ssas = self.insert_qubit_idx_ssa(apply_stmt=apply_stmt)
        stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas))
        stim_1q_stmt.insert_before(apply_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_Control(
        self, apply_stmt_ctrl: qubit.Apply | wire.Apply
    ) -> RewriteResult:
        # stim only supports CX, CY, CZ so we have to check the
        # operator of Apply is a Control gate, enforce it's only asking for 1 control qubit,
        # and that the target of the control is X, Y, Z in squin

        ctrl_op: op.stmts.Control = apply_stmt_ctrl.operator.owner
        # enforce that n_controls is 1

        ctrl_op_target_gate = ctrl_op.op.owner

        # should enforce that this is some multiple of 2
        qubit_idx_ssas = self.insert_qubit_idx_ssa(apply_stmt=apply_stmt_ctrl)
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
            # qubits are in an ilist which makes up an AddressTuple
            address_tuple: AddressTuple = self.get_address(qubit_ilist_ssa).address
            qubit_idx_ssas = []
            for qubit_address in address_tuple:
                qubit_idx = qubit_address.data
                qubit_idx_stmt = py.constant.Constant(qubit_idx)
                qubit_idx_stmt.insert_before(measure_stmt)
                qubit_idx_ssas.append(qubit_idx_stmt.result)
            qubit_idx_ssas = tuple(qubit_idx_ssas)

        elif isinstance(measure_stmt, wire.Measure):
            wire_ssa = measure_stmt.wire
            wire_address: AddressWire = self.get_address(wire_ssa).address

            qubit_idx = wire_address.origin_qubit.data
            qubit_idx_stmt = py.constant.Constant(qubit_idx)
            qubit_idx_stmt.insert_before(measure_stmt)
            qubit_idx_ssas = (qubit_idx_stmt.result,)

        else:
            return RewriteResult()

        prob_noise_stmt = py.constant.Constant(0.0)
        stim_measure_stmt = stim.collapse.MZ(
            p=prob_noise_stmt.result,
            targets=qubit_idx_ssas,
        )
        prob_noise_stmt.insert_before(measure_stmt)
        stim_measure_stmt.insert_before(measure_stmt)

        return RewriteResult(has_done_something=True)
