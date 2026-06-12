from dataclasses import dataclass, field

from kirin import ir, passes
from kirin.dialects.ilist.runtime import IList
from kirin.dialects.func.stmts import Invoke
from kirin.ir.attrs.types import Generic, Literal, PyClass
from kirin.rewrite import Walk, Chain, DeadCodeElimination
from kirin.rewrite.abc import RewriteRule, RewriteResult

from .callgraph import CallGraphPass

_ILIST_BODY = PyClass(IList)


def _has_empty_ilist_input(node: Invoke) -> bool:
    for inp in node.inputs:
        t = inp.type
        if not isinstance(t, Generic):
            continue
        if t.body != _ILIST_BODY:
            continue
        if len(t.vars) < 2:
            continue
        len_var = t.vars[1]
        if isinstance(len_var, Literal) and len_var.data == 0:
            return True
    return False


class RemoveEmptyArgGatesRule(RewriteRule):
    """Delete Invoke statements whose qubit-list argument is a compile-time empty IList."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, Invoke):
            return RewriteResult()
        if not _has_empty_ilist_input(node):
            return RewriteResult()
        node.delete(safe=False)
        return RewriteResult(has_done_something=True)


@dataclass
class RemoveEmptyArgGates(passes.Pass):
    """Remove squin gate/noise/measurement calls on empty qubit lists.

    Usage::

        RemoveEmptyArgGates(main.dialects)(main)
    """

    _inner: CallGraphPass = field(init=False, repr=False)

    def __post_init__(self) -> None:
        rule = Walk(Chain(RemoveEmptyArgGatesRule(), DeadCodeElimination()))
        self._inner = CallGraphPass(
            rule=rule,
            dialects=self.dialects,
            no_raise=self.no_raise,
        )

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        return self._inner.unsafe_run(mt)
