from dataclasses import field, dataclass

from kirin import ir
from kirin.dialects import py, scf, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import gate
from bloqade.rewrite.rules import LiftThenBody, SplitIfStmts
from bloqade.squin.rewrite import AddressAttribute
from bloqade.stim.rewrite.util import (
    insert_qubit_idx_from_address,
)
from bloqade.stim.dialects.gate import CX as stim_CX, CY as stim_CY, CZ as stim_CZ
from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.stim.dialects.auxiliary import GetRecord
from bloqade.analysis.measure_id.lattice import (
    MeasureIdBool,
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
class IfToStim(IfElseSimplification, RewriteRule):
    """
    Rewrite if statements to stim equivalent statements.
    """

    measure_frame: MeasureIDFrame

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case scf.IfElse():
                return self.rewrite_IfElse(node)
            case _:
                return RewriteResult()

    def rewrite_IfElse(self, stmt: scf.IfElse) -> RewriteResult:

        # Check the condition is a singular MeasurementIdBool
        if not isinstance(self.measure_frame.entries[stmt.cond], MeasureIdBool):
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

        # get necessary measurement ID type from analysis
        measure_id_bool = self.measure_frame.entries[stmt.cond]
        assert isinstance(measure_id_bool, MeasureIdBool)

        # generate get record statement
        measure_id_idx_stmt = py.Constant(
            (measure_id_bool.idx - 1) - self.measure_frame.num_measures_at_stmt[stmt]
        )
        get_record_stmt = GetRecord(id=measure_id_idx_stmt.result)  # noqa: F841

        address_attr = stmts[0].qubits.hints.get("address")

        if address_attr is None:
            return RewriteResult()
        assert isinstance(address_attr, AddressAttribute)

        # note: insert things before (literally above/outside) the If
        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=stmt
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
