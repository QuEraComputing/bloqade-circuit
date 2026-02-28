from dataclasses import dataclass

from kirin import types
from kirin.ir import Method
from kirin.passes import Pass
from kirin.rewrite import Walk
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.ir.nodes.stmt import Statement

from ..dialects.operations.stmts import TerminalLogicalMeasurement


@dataclass
class _DeleteBelowTerminalMeasure(RewriteRule):
    has_seen_terminal_measure: bool = False

    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        if isinstance(node, func.Function):
            # NOTE: this is a flat kernel, so the only function we should
            # have is the callable_region of the kernel; don't delete that
            return RewriteResult()

        if isinstance(node, func.Return):
            # NOTE: leave return values unchanged, handled in separate rule
            return RewriteResult()

        if isinstance(node, TerminalLogicalMeasurement):
            self.has_seen_terminal_measure = True
            return RewriteResult()

        if not self.has_seen_terminal_measure:
            # we are still above the terminal measurement
            return RewriteResult()

        # post-processing logic here
        for result in node.results:
            for use in result.uses:
                if isinstance(use.stmt, func.Return):
                    return RewriteResult()

        # NOTE: we need to use unsafe deletion here since the node may have
        # uses below, but any statements that use it will be deleted, except
        # for the return which is handled above
        node.delete(safe=False)
        return RewriteResult(has_done_something=True)


class _RewriteReturnToNone(RewriteRule):
    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        if isinstance(node, func.Function):
            if node.signature.output.is_subseteq(types.NoneType):
                return RewriteResult()
            # need to update signature to return None
            new_signature = func.Signature(node.signature.inputs, types.NoneType)
            node.signature = new_signature
            return RewriteResult(has_done_something=True)

        if not isinstance(node, func.Return):
            return RewriteResult()

        # check if we already return None
        if (
            isinstance(node.value.owner, py.Constant)
            and node.value.owner.value.unwrap() is None
        ):
            return RewriteResult()

        none_value = py.Constant(None)
        none_value.insert_before(node)
        node.replace_by(func.Return(none_value.result))

        return RewriteResult(has_done_something=True)


class RemovePostProcessing(Pass):
    """Remove post-processing steps, i.e. everything below a TerminalMeasure statement
    in a logical kernel.

    The return value is changed to return None.

    **NOTE**: Expects a flat logical kernel. Otherwise may lead to incorrect results.
    """

    def unsafe_run(self, mt: Method) -> RewriteResult:
        result = Walk(_RewriteReturnToNone()).rewrite(mt.code)

        Walk(_DeleteBelowTerminalMeasure()).rewrite(mt.code).join(result)
        return result
