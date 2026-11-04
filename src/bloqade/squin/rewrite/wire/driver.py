"""Run bounded rewrites, insert replacement statements, and reject recursion.

`put` and `replace` are the 2 steps that every rewrite rule of the wire
conversions uses to swap a statement for its replacement.
"""

from typing import TypeVar
from dataclasses import field, dataclass
from collections.abc import Callable

from kirin import ir
from kirin.rewrite import Walk, Fixpoint
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin.wire.errors import WireConversionError

StatementT = TypeVar("StatementT", bound=ir.Statement)


def put(stmt: StatementT, before: ir.Statement) -> StatementT:
    """Insert `stmt` before the statement `before` and return `stmt`."""
    stmt.insert_before(before)
    return stmt


def replace(node: ir.Statement, *values: ir.SSAValue) -> None:
    """Replace each result of `node` with the value at its position and delete `node`."""
    for result, value in zip(node.results, values, strict=True):
        result.replace_by(value)
    node.delete()


@dataclass
class CheckedFixpoint(Fixpoint):
    """Report exhaustion of Kirin's rewrite limit as a conversion failure."""

    def rewrite(self, node: ir.IRNode) -> RewriteResult:
        """Run the rules until convergence or report the configured iteration limit."""
        result = super().rewrite(node)
        if result.exceeded_max_iter:
            raise WireConversionError(
                f"Wire rewriting did not converge within {self.max_iter} iterations.",
                node,
            )
        return result


@dataclass
class Calls(RewriteRule):
    """Collect static callees through Kirin's walker."""

    callees: dict[ir.Method, None] = field(default_factory=dict)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Record each direct call without changing its statement."""
        if isinstance(node, func.Invoke):
            self.callees[node.callee] = None
        return RewriteResult()


def reachable(
    method: ir.Method, skip: Callable[[ir.Method], bool] = lambda _: False
) -> list[ir.Method]:
    """Return reachable methods and reject call cycles before conversion or validation."""
    done: dict[ir.Method, None] = {}
    active: set[ir.Method] = set()

    def visit(current: ir.Method) -> None:
        if current in active:
            raise WireConversionError(
                f"Wire conversion does not support recursive calls to '{current.sym_name}'.",
                current.code,
            )
        if current in done or skip(current):
            return
        active.add(current)
        calls = Calls()
        Walk(calls).rewrite(current.code)
        for callee in calls.callees:
            visit(callee)
        active.remove(current)
        done[current] = None

    visit(method)
    return list(done)
