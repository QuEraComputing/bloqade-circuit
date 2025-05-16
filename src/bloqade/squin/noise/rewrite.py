from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import Walk
from kirin.dialects import ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from .stmts import (
    PPError,
    QubitLoss,
    Depolarize,
    PauliError,
    NoiseChannel,
    PauliChannel,
    StochasticUnitaryChannel,
)


class _RewriteNoiseStmts(RewriteRule):
    """Rewrites squin noise statements to StochasticUnitaryChannel"""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, NoiseChannel):
            return RewriteResult()

        if isinstance(node, QubitLoss):
            return RewriteResult()

        return getattr(self, "rewrite_" + node.name)(node)

    def rewrite_pauli_error(self, node: PauliError) -> RewriteResult:
        (operators := ilist.New(values=(node.basis,))).insert_before(node)
        (ps := ilist.New(values=(node.p,))).insert_before(node)
        stochastic_channel = StochasticUnitaryChannel(
            operators=operators.result, probabilities=ps.result
        )

        node.replace_by(stochastic_channel)
        return RewriteResult(has_done_something=True)

    def rewrite_pauli_channel(self, node: PauliChannel) -> RewriteResult:
        # TODO
        return RewriteResult(has_done_something=False)

    def rewrite_pp_error(self, node: PPError) -> RewriteResult:
        (operators := ilist.New(values=(node.op,))).insert_before(node)
        (ps := ilist.New(values=(node.p,))).insert_before(node)
        stochastic_channel = StochasticUnitaryChannel(
            operators=operators.result, probabilities=ps.result
        )

        node.replace_by(stochastic_channel)
        return RewriteResult(has_done_something=True)

    def rewrite_depolarize(self, node: Depolarize) -> RewriteResult:
        # TODO
        return RewriteResult(has_done_something=False)


class RewriteNoiseStmts(Pass):
    def unsafe_run(self, mt: ir.Method):
        return Walk(_RewriteNoiseStmts()).rewrite(mt.code)
