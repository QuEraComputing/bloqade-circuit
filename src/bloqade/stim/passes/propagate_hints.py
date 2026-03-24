from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.scf.stmts import For


class PropagateHintsIntoForBody(RewriteRule):
    """Propagate hints from scf.For initializers to body block args.

    When scf.For loops are preserved (not unrolled), the body block args
    are separate SSA values from the initializers. Passes like
    WrapAddressAnalysis set hints on the initializer SSA values but not
    on the body block args. This rule copies hints from initializers to
    the corresponding body block args so downstream conversion passes
    (SquinQubitToStim, SquinMeasureToStim, etc.) can process the body.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, For):
            return RewriteResult()

        body_block = node.body.blocks[0]
        # body block args: [loop_var, *loop_state_vars]
        # initializers correspond to loop_state_vars
        for block_arg, init in zip(body_block.args[1:], node.initializers):
            for key, value in init.hints.items():
                if key not in block_arg.hints:
                    block_arg.hints[key] = value

        return RewriteResult()
