from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import ForwardFrame
from kirin.dialects import py, scf, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import gate
from bloqade.rewrite.rules import LiftThenBody, SplitIfStmts
from bloqade.stim.rewrite.util import (
    insert_qubit_idx_from_address,
)
from bloqade.stim.dialects.gate import CX as stim_CX, CY as stim_CY, CZ as stim_CZ
from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.stim.dialects.auxiliary import GetRecord
from bloqade.analysis.measure_id.lattice import (
    Predicate,
    RawMeasureId,
    InvalidMeasureId,
)


@dataclass
class IfElseSimplification:

    # Might be better to just do a rewrite_Region?
    def is_rewriteable(self, node: scf.IfElse) -> bool:
        return not (
            self.contains_ifelse(node)
            or self.is_nested_ifelse(node)
            or self.has_else_body(node)
        )

    # A preliminary check to reject an IfElse from the "top down"
    # use in conjunction with is_nested_ifelse
    # to completely cover cases of nested IfElse statements
    def contains_ifelse(self, stmt: scf.IfElse) -> bool:
        """Check if the IfElse statement contains another IfElse statement."""
        for child in stmt.walk(include_self=False):
            if isinstance(child, scf.IfElse):
                return True
        return False

    # because rewrite latches onto ANY scf.IfElse,
    # you need a way to determine if you're touching an
    # IfElse that's inside another IfElse
    def is_nested_ifelse(self, stmt: scf.IfElse) -> bool:
        """Check if the IfElse statement is nested."""
        if stmt.parent_stmt is not None:
            if isinstance(stmt.parent_stmt, scf.IfElse) or isinstance(
                stmt.parent_stmt.parent_stmt, scf.IfElse
            ):
                return True
            else:
                return False
        else:
            return False

    def has_else_body(self, stmt: scf.IfElse) -> bool:
        """Check if the IfElse statement has an else body."""
        if stmt.else_body.blocks and not (
            len(stmt.else_body.blocks[0].stmts) == 1
            and isinstance(stmt.else_body.blocks[0].last_stmt, scf.Yield)
        ):
            return True

        return False


DontLiftType = (
    gate.stmts.SingleQubitGate,
    gate.stmts.RotationGate,
    gate.stmts.ControlledGate,
    func.Return,
    func.Invoke,
    scf.IfElse,
    scf.Yield,
)


@dataclass
class StimLiftThenBody(IfElseSimplification, LiftThenBody):
    exclude_stmts: tuple[type[ir.Statement], ...] = field(default=DontLiftType)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if not isinstance(node, scf.IfElse):
            return RewriteResult()

        if not self.is_rewriteable(node):
            return RewriteResult()

        return super().rewrite_Statement(node)


# Only run this after everything other than qubit.Apply/qubit.Broadcast has been
# lifted out!
class StimSplitIfStmts(IfElseSimplification, SplitIfStmts):
    """Splits the then body of an if-else statement into multiple if statements

    Given an IfElse with multiple valid statements in the then-body:

    if measure_result:
        squin.x(q0)
        squin.y(q1)

    this should be rewritten to:

    if measure_result:
        squin.x(q0)

    if measure_result:
        squin.y(q1)
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, scf.IfElse):
            return RewriteResult()

        if not self.is_rewriteable(node):
            return RewriteResult()

        return super().rewrite_Statement(node)


@dataclass
class BreakIfChainConditionDependency(IfElseSimplification, RewriteRule):
    """Removes dependency chain from condition for IfElse statements
    being yield to subsequent IfElse statements that occurs from lowering
    when the conditions are the same.

    For example, given:

    if a:
        ...

    if a:
        ...

    Kirin makes the first IfElse statement yield its condition to the second IfElse statement to
    account for the possibility that the first IfElse statement can mutate the condition.

    However, there is no equivalent representation of this behavior in Stim and the chaining of IfElse's
    causes issues with subsequent rewrites to valid feedforward statements in Stim. To resolve this,
    this rewrite rule simply replaces the yielded condition with the original condition.

    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, scf.IfElse):
            return RewriteResult()

        if not self.is_rewriteable(node):
            return RewriteResult()

        # Check exactly one result
        if len(node.results) != 1:
            return RewriteResult()

        # Replace the result with the condition
        node.results[0].replace_by(node.cond)

        # Remove the yielded values from both branches
        for region in node.regions:
            for block in region.blocks:
                if isinstance(block.last_stmt, scf.Yield):
                    block.last_stmt.args = []

        node._results = []

        return RewriteResult(has_done_something=True)


@dataclass
class IfToStim(IfElseSimplification, RewriteRule):
    """
    Rewrite if statements to stim equivalent statements.
    """

    measure_frame: MeasureIDFrame
    address_frame: ForwardFrame

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case scf.IfElse():
                return self.rewrite_IfElse(node)
            case _:
                return RewriteResult()

    def rewrite_IfElse(self, stmt: scf.IfElse) -> RewriteResult:

        condition_type = self.measure_frame.type_for_scf_conds.get(stmt)
        if condition_type is None or condition_type is InvalidMeasureId():
            return RewriteResult()

        if not isinstance(condition_type, RawMeasureId):
            return RewriteResult()

        if condition_type.predicate != Predicate.IS_ONE:
            return RewriteResult()

        # Reusing code from SplitIf,
        # there should only be one statement in the body and it should be a pauli X, Y, or Z
        *stmts, _ = stmt.then_body.stmts()
        if len(stmts) != 1:
            return RewriteResult()

        if isinstance(stmts[0], gate.stmts.X):
            stim_gate = stim_CX
        elif isinstance(stmts[0], gate.stmts.Y):
            stim_gate = stim_CY
        elif isinstance(stmts[0], gate.stmts.Z):
            stim_gate = stim_CZ
        else:
            return RewriteResult()

        # generate get record statement
        measure_id_idx_stmt = py.Constant(condition_type.idx)
        get_record_stmt = GetRecord(id=measure_id_idx_stmt.result)

        address_lattice_elem = self.address_frame.entries.get(stmts[0].qubits)

        if address_lattice_elem is None:
            return RewriteResult()
        # note: insert things before (literally above/outside) the If
        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_lattice_elem, stmt_to_insert_before=stmt
        )
        if qubit_idx_ssas is None:
            return RewriteResult()

        # Assemble the stim statement
        # let GetRecord's SSA be repeated per each get qubit
        ctrl_records = tuple(get_record_stmt.result for _ in qubit_idx_ssas)

        stim_stmt = stim_gate(
            targets=tuple(qubit_idx_ssas),
            controls=ctrl_records,
        )

        # Insert the necessary SSA Values, then get rid of the scf.IfElse.
        # The qubit indices have been successfully added,
        # that just leaves the GetRecord statement and measurement ID index statement

        measure_id_idx_stmt.insert_before(stmt)
        get_record_stmt.insert_before(stmt)
        stmt.replace_by(stim_stmt)

        return RewriteResult(has_done_something=True)
