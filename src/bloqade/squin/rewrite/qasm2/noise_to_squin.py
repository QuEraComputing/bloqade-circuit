from kirin import ir
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects.noise import stmts as noise_stmts


class QASM2NoiseToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case noise_stmts.AtomLossChannel():
                return self.rewrite_AtomLossChannel(node)
            case noise_stmts.PauliChannel():
                return self.rewrite_PauliChannel(node)
            case noise_stmts.CZPauliChannel():
                return self.rewrite_CZPauliChannel(node)
            case _:
                return RewriteResult()

        return RewriteResult()

    def rewrite_AtomLossChannel(
        self, stmt: noise_stmts.AtomLossChannel
    ) -> RewriteResult:

        qargs = stmt.qargs
        # this is a raw float, not in SSA form yet!
        prob = stmt.prob
        prob_stmt = py.Constant(value=prob)
        prob_stmt.insert_before(stmt)

        invoke_loss_stmt = func.Invoke(
            callee=squin.broadcast.qubit_loss,
            inputs=(prob_stmt.result, qargs),
        )

        stmt.replace_by(invoke_loss_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_PauliChannel(self, stmt: noise_stmts.PauliChannel) -> RewriteResult:

        qargs = stmt.qargs
        p_x = stmt.px
        p_y = stmt.py
        p_z = stmt.pz

        probs = [p_x, p_y, p_z]
        probs_ssas = []

        for prob in probs:
            prob_stmt = py.Constant(value=prob)
            prob_stmt.insert_before(stmt)
            probs_ssas.append(prob_stmt.result)

        invoke_pauli_channel_stmt = func.Invoke(
            callee=squin.broadcast.single_qubit_pauli_channel,
            inputs=(*probs_ssas, qargs),
        )

        stmt.replace_by(invoke_pauli_channel_stmt)
        return RewriteResult(has_done_something=True)

    def rewrite_CZPauliChannel(self, stmt: noise_stmts.CZPauliChannel) -> RewriteResult:

        ctrls = stmt.ctrls
        qargs = stmt.qargs

        px_ctrl = stmt.px_ctrl
        py_ctrl = stmt.py_ctrl
        pz_ctrl = stmt.pz_ctrl
        px_qarg = stmt.px_qarg
        py_qarg = stmt.py_qarg
        pz_qarg = stmt.pz_qarg

        error_probs = [px_ctrl, py_ctrl, pz_ctrl, px_qarg, py_qarg, pz_qarg]
        # first half of entries for control qubits, other half for targets
        error_prob_ssas = []
        for error_prob in error_probs:
            error_prob_stmt = py.Constant(value=error_prob)
            error_prob_stmt.insert_before(stmt)
            error_prob_ssas.append(error_prob_stmt.result)

        ctrl_pauli_channel_invoke = func.Invoke(
            callee=squin.broadcast.single_qubit_pauli_channel,
            inputs=(
                *error_prob_ssas[:3],
                ctrls,
            ),
        )

        qarg_pauli_channel_invoke = func.Invoke(
            callee=squin.broadcast.single_qubit_pauli_channel,
            inputs=(
                *error_prob_ssas[3:],
                qargs,
            ),
        )

        ctrl_pauli_channel_invoke.insert_before(stmt)
        qarg_pauli_channel_invoke.insert_before(stmt)
        stmt.delete()

        return RewriteResult(has_done_something=True)
