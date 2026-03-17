from dataclasses import field, dataclass

from kirin import ir
from kirin.dialects import scf, func
from kirin.rewrite.abc import RewriteResult

from bloqade.squin import gate
from bloqade.rewrite.rules import LiftThenBody, SplitIfStmts


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
