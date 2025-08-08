import itertools

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import Walk
from kirin.dialects import py, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from .stmts import (
    QubitLoss,
    Depolarize,
    PauliError,
    Depolarize2,
    NoiseChannel,
    TwoQubitPauliChannel,
    SingleQubitPauliChannel,
    StochasticUnitaryChannel,
)
from ..op.stmts import X, Y, Z, Kron, Identity


class _RewriteNoiseStmts(RewriteRule):
    """Rewrites squin noise statements to StochasticUnitaryChannel"""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, NoiseChannel) or isinstance(node, QubitLoss):
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

    def rewrite_single_qubit_pauli_channel(
        self, node: SingleQubitPauliChannel
    ) -> RewriteResult:
        paulis = (X(), Y(), Z())
        paulis_ssa: list[ir.SSAValue] = []
        for op in paulis:
            op.insert_before(node)
            paulis_ssa.append(op.result)

        (pauli_ops := ilist.New(values=paulis_ssa)).insert_before(node)

        stochastic_unitary = StochasticUnitaryChannel(
            operators=pauli_ops.result, probabilities=node.params
        )
        node.replace_by(stochastic_unitary)
        return RewriteResult(has_done_something=True)

    def rewrite_two_qubit_pauli_channel(
        self, node: TwoQubitPauliChannel
    ) -> RewriteResult:
        operator_list = self._insert_two_qubit_paulis_before_node(node)
        stochastic_unitary = StochasticUnitaryChannel(
            operators=operator_list, probabilities=node.params
        )

        node.replace_by(stochastic_unitary)
        return RewriteResult(has_done_something=True)

    @staticmethod
    def _insert_two_qubit_paulis_before_node(
        node: TwoQubitPauliChannel | Depolarize2,
    ) -> ir.ResultValue:
        paulis = (Identity(sites=1), X(), Y(), Z())
        for op in paulis:
            op.insert_before(node)

        # NOTE: collect list so we can skip the first entry, which will be two identities
        combinations = list(itertools.product(paulis, repeat=2))[1:]
        operators: list[ir.SSAValue] = []
        for pauli_1, pauli_2 in combinations:
            op = Kron(pauli_1.result, pauli_2.result)
            op.insert_before(node)
            operators.append(op.result)

        (operator_list := ilist.New(values=operators)).insert_before(node)
        return operator_list.result

    def rewrite_depolarize(self, node: Depolarize) -> RewriteResult:
        paulis = (X(), Y(), Z())
        operators: list[ir.SSAValue] = []
        for op in paulis:
            op.insert_before(node)
            operators.append(op.result)

        # NOTE: need to divide the probability by 3 to get the correct total error rate
        (three := py.Constant(3)).insert_before(node)
        (p_over_3 := py.Div(node.p, three.result)).insert_before(node)

        (operator_list := ilist.New(values=operators)).insert_before(node)
        (ps := ilist.New(values=[p_over_3.result for _ in range(3)])).insert_before(
            node
        )

        stochastic_unitary = StochasticUnitaryChannel(
            operators=operator_list.result, probabilities=ps.result
        )
        node.replace_by(stochastic_unitary)

        return RewriteResult(has_done_something=True)

    def rewrite_depolarize2(self, node: Depolarize2) -> RewriteResult:
        operator_list = self._insert_two_qubit_paulis_before_node(node)

        # NOTE: need to divide the probability by 15 to get the correct total error rate
        (fifteen := py.Constant(15)).insert_before(node)
        (p_over_15 := py.Div(node.p, fifteen.result)).insert_before(node)
        (probs := ilist.New(values=[p_over_15.result] * 15)).insert_before(node)

        stochastic_unitary = StochasticUnitaryChannel(
            operators=operator_list, probabilities=probs.result
        )
        node.replace_by(stochastic_unitary)

        return RewriteResult(has_done_something=True)


class RewriteNoiseStmts(Pass):
    def unsafe_run(self, mt: ir.Method):
        return Walk(_RewriteNoiseStmts()).rewrite(mt.code)
