from kirin.rewrite import Walk, Chain
from kirin.passes.inline import InlinePass

from bloqade import qasm2, squin
from bloqade.qasm2 import glob, noise, parallel

# from kirin import prelude
# from kirin.passes import Fold, TypeInfer
# from kirin.dialects.ilist.passes import IListDesugar
from bloqade.squin.passes import QASM2ToSquin
from bloqade.squin.rewrite.qasm2 import (
    QASM2CoreToSquin,
    QASM2ExprToSquin,
)


def test_expr_rewrite():

    @qasm2.main
    def expr_program():
        x = 0
        z = -1.7
        y = x + z
        qasm2.sin(y)
        return y

    Walk(QASM2ExprToSquin()).rewrite(expr_program.code)

    expr_program.print()


def test_qasm2_core():

    @qasm2.main(fold=False)
    def measure_kern():
        q = qasm2.qreg(5)
        q0 = q[0]
        return q0

    measure_kern.print()

    Walk(Chain(QASM2ExprToSquin(), QASM2CoreToSquin())).rewrite(measure_kern.code)

    measure_kern.print()


def test_gates():

    @qasm2.main
    def gate_program():
        q = qasm2.qreg(10)
        qasm2.cx(q[0], q[1])
        qasm2.z(q[3])
        qasm2.u3(q[4], 1.57, 0.0, 3.14)
        qasm2.u1(q[5], 0.78)
        qasm2.rz(q[6], 2.34)
        qasm2.sx(q[7])
        return q

    gate_program.print()
    QASM2ToSquin(dialects=squin.kernel)(gate_program)
    gate_program.print()


def test_noise():

    @qasm2.extended
    def noise_program():
        q = qasm2.qreg(4)
        noise.atom_loss_channel(qargs=q, prob=0.05)
        noise.pauli_channel(qargs=q, px=0.01, py=0.02, pz=0.03)
        noise.cz_pauli_channel(
            ctrls=[q[0], q[1]],
            qargs=[q[2], q[3]],
            px_ctrl=0.01,
            py_ctrl=0.02,
            pz_ctrl=0.03,
            px_qarg=0.04,
            py_qarg=0.05,
            pz_qarg=0.06,
            paired=True,
        )
        return q

    noise_program.print()
    QASM2ToSquin(dialects=squin.kernel)(noise_program)
    InlinePass(dialects=squin.kernel)(noise_program)


def test_global_and_parallel():

    @qasm2.extended
    def global_parallel_program():
        q = qasm2.qreg(6)
        parallel.u([q[0]], 1.0, 0.0, 3.14)
        glob.u([q[1], q[2], q[3]], 0.5, 1.57, 0.0)
        parallel.rz([q[4], q[5]], 2.34)

        return q

    global_parallel_program.print()
    QASM2ToSquin(dialects=squin.kernel)(global_parallel_program)
    InlinePass(dialects=squin.kernel)(global_parallel_program)
    global_parallel_program.print()
