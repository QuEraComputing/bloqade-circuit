from kirin import ir
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects.noise import stmts as noise_stmts

NOISE_TO_SQUIN_MAP = {
    noise_stmts.AtomLossChannel: squin.broadcast.qubit_loss,
    noise_stmts.PauliChannel: squin.broadcast.single_qubit_pauli_channel,
}


def num_to_py_constant(
    values: list[int | float], stmt_to_insert_before: ir.Statement
) -> list[ir.SSAValue]:

    py_const_ssa_vals = []
    for value in values:
        const_form = py.Constant(value=value)
        const_form.insert_before(stmt_to_insert_before)
        py_const_ssa_vals.append(const_form.result)

    return py_const_ssa_vals


class QASM2NoiseToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if isinstance(node, noise_stmts.AtomLossChannel):
            qargs = node.qargs
            prob = node.prob
            prob_ssas = num_to_py_constant([prob], stmt_to_insert_before=node)
        elif isinstance(node, noise_stmts.PauliChannel):
            qargs = node.qargs
            p_x = node.px
            p_y = node.py
            p_z = node.pz
            prob_ssas = num_to_py_constant([p_x, p_y, p_z], stmt_to_insert_before=node)
        elif isinstance(node, noise_stmts.CZPauliChannel):
            return self.rewrite_CZPauliChannel(node)
        else:
            return RewriteResult()

        squin_noise_stmt = NOISE_TO_SQUIN_MAP[type(node)]
        invoke_stmt = func.Invoke(
            callee=squin_noise_stmt,
            inputs=(*prob_ssas, qargs),
        )
        node.replace_by(invoke_stmt)
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

        error_prob_ssas = num_to_py_constant(error_probs, stmt_to_insert_before=stmt)

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
