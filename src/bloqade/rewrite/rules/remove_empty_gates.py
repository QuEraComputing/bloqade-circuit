from kirin import ir, types
from kirin.ir import traits
from kirin.dialects import func, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.func.stmts import Invoke

from bloqade.squin import gate, noise
from bloqade.qubit import stmts as qubit_stmts

# Statements that apply an operation to a list of qubits. Applying any of them to
# an empty list is a no-op.
QubitOp = (
    gate.stmts.Gate,
    noise.stmts.NoiseChannel,
    qubit_stmts.Measure,
    qubit_stmts.Reset,
)


def _is_empty_ilist(value: ir.SSAValue) -> bool:
    t = value.type
    if not (isinstance(t, types.Generic) and t.is_subseteq(ilist.IListType)):
        return False
    _, length = t.vars
    return isinstance(length, types.Literal) and length.data == 0


def _operates_on_empty_qubits(stmt: ir.Statement) -> bool:
    args = [
        getattr(stmt, name)
        for name in ("qubits", "controls", "targets")
        if hasattr(stmt, name)
    ]
    return bool(args) and all(_is_empty_ilist(arg) for arg in args)


def _is_qubit_op_wrapper(method: ir.Method) -> bool:
    """True if the only effect of the method is applying qubit ops to qubit lists.

    Such a method is a no-op when all of its qubit-list arguments are empty.
    """
    for stmt in method.callable_region.walk():
        if isinstance(stmt, (func.Function, func.Return, QubitOp)):
            continue
        if stmt.has_trait(traits.Pure):
            continue
        if isinstance(stmt, Invoke) and _is_qubit_op_wrapper(stmt.callee):
            continue
        return False
    return True


class RemoveEmptyGate(RewriteRule):
    """Remove gate, noise and measurement statements applied to empty qubit lists."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, QubitOp) or not _operates_on_empty_qubits(node):
            return RewriteResult()
        if any(result.uses for result in node.results):
            return RewriteResult()
        node.delete()
        return RewriteResult(has_done_something=True)


class RemoveEmptyGateCall(RewriteRule):
    """Remove invocations of qubit-op wrappers (e.g. broadcast gates) on empty lists."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, Invoke) or any(result.uses for result in node.results):
            return RewriteResult()

        qubit_args = [arg for arg in node.inputs if _is_empty_ilist(arg)]
        if not qubit_args or not _is_qubit_op_wrapper(node.callee):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)
