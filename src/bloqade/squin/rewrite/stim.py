from typing import Dict
from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.print.printer import Printer

from bloqade import stim
from bloqade.squin import op, wire, qubit
from bloqade.analysis.address import Address
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
class SquinToStim(RewriteRule):

    def get_address(self, value: ir.SSAValue):
        return value.hints.get("address")

    def get_sites(self, value: ir.SSAValue):
        return value.hints.get("sites")

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
            case _:
                return None

    # might be worth attempting multiple dispatch like qasm2 rewrites
    # for Glob and Parallel to UOp
    # The problem is I'd have to introduce names for all the statements
    # as a ClassVar str. Maybe hold off for now.

    # Don't translate constants to Stim Aux Constants just yet,
    # The Stim operations don't even rely on those particular
    # constants, seems to be more for lowering from Python AST

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        pass

    def rewrite_Apply(self, apply_stmt: qubit.Apply | wire.Apply) -> RewriteResult:

        # this is an SSAValue, need it to be the actual operator
        applied_op = apply_stmt.operator.owner

        # need to handle Identity and Control through separate means
        # but we can handle X, Y, Z, and H here just fine
        stim_1q_op = self.get_stim_1q_gate(applied_op)

        if isinstance(apply_stmt, qubit.Apply):
            qubits = apply_stmt.qubits
            address_attribute: AddressAttribute = self.get_address(qubits)
            # Should get an AddressTuple out of the address stored in attribute
            address_tuple = address_attribute.address
            qubit_idx_ssas: list[ir.SSAValue] = []
            for address_qubit in address_tuple.data:
                qubit_idx = address_qubit.data
                qubit_idx_stmt = py.Constant(qubit_idx)
                qubit_idx_ssas.append(qubit_idx_stmt.result)
                qubit_idx_stmt.insert_before(apply_stmt)

            stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas))

            apply_stmt.replace_by(stim_1q_stmt)
            apply_stmt.delete()

            return RewriteResult(has_done_something=True)

        elif isinstance(apply_stmt, wire.Apply):
            wires_ssa = apply_stmt.inputs
            qubit_idx_ssas: list[ir.SSAValue] = []
            for wire_ssa in wires_ssa:
                address_attribute = self.get_address(wire_ssa)
                # get parent qubit idx
                wire_address = address_attribute.data
                qubit_idx = wire_address.origin_qubit.data
                qubit_idx_stmt = py.Constant(qubit_idx)
                qubit_idx_ssas.append(qubit_idx_stmt.result)
                qubit_idx_stmt.insert_before(apply_stmt)

            stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas))

            apply_stmt.replace_by(stim_1q_stmt)
            apply_stmt.delete()

            return RewriteResult(has_done_something=True)

        return RewriteResult()
