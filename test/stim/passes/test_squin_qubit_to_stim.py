import os
import math

from kirin import ir
from kirin.dialects import py

from bloqade import squin
from bloqade.squin import op, noise, qubit, kernel
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass


# Taken gratuitously from Kai's unit test
def codegen(mt: ir.Method):
    # method should not have any arguments!
    emit = EmitStimMain()
    emit.initialize()
    emit.run(mt=mt, args=())
    return emit.get_output()


def as_int(value: int):
    return py.constant.Constant(value=value)


def as_float(value: float):
    return py.constant.Constant(value=value)


def load_reference_program(filename):
    path = os.path.join(
        os.path.dirname(__file__), "stim_reference_programs", "qubit", filename
    )
    with open(path, "r") as f:
        return f.read()


def test_qubit():
    @kernel
    def test():
        n_qubits = 2
        ql = qubit.new(n_qubits)
        qubit.broadcast(op.h(), ql)
        qubit.apply(op.x(), ql[0])
        ctrl = op.control(op.x(), n_controls=1)
        qubit.apply(ctrl, ql[1], ql[0])
        # measure out
        squin.qubit.measure(ql)
        return

    test.print()

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("qubit.stim")

    assert codegen(test) == base_stim_prog.rstrip()


def test_qubit_reset():
    @kernel
    def test():
        n_qubits = 1
        q = qubit.new(n_qubits)
        # reset the qubit
        squin.qubit.apply(op.reset(), q[0])
        # measure out
        squin.qubit.measure(q[0])
        return

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("qubit_reset.stim")

    assert codegen(test) == base_stim_prog.rstrip()


def test_qubit_broadcast():
    @kernel
    def test():
        n_qubits = 4
        ql = qubit.new(n_qubits)
        # apply Hadamard to all qubits
        squin.qubit.broadcast(op.h(), ql)
        # measure out
        squin.qubit.measure(ql)
        return

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("qubit_broadcast.stim")

    assert codegen(test) == base_stim_prog.rstrip()


def test_qubit_loss():
    @kernel
    def test():
        n_qubits = 5
        ql = qubit.new(n_qubits)
        # apply Hadamard to all qubits
        squin.qubit.broadcast(op.h(), ql)
        # apply and broadcast qubit loss
        squin.qubit.apply(noise.qubit_loss(0.1), ql[3])
        squin.qubit.broadcast(noise.qubit_loss(0.05), ql)
        # measure out
        squin.qubit.measure(ql)
        return

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("qubit_loss.stim")

    assert codegen(test) == base_stim_prog.rstrip()


def test_adjoint_rewrite():

    @squin.kernel
    def test():
        q = qubit.new(1)
        sqrt_x_dag = op.adjoint(op.sqrt_x())
        sqrt_y_dag = op.adjoint(op.sqrt_y())
        sqrt_s_dag = op.adjoint(op.s())
        qubit.apply(sqrt_x_dag, q[0])
        qubit.apply(sqrt_y_dag, q[0])
        qubit.apply(sqrt_s_dag, q[0])
        return

    SquinToStimPass(test.dialects)(test)

    base_stim_prog = load_reference_program("adjoint_rewrite.stim")

    assert codegen(test) == base_stim_prog.rstrip()


def test_u3_to_clifford():

    @kernel
    def test():
        n_qubits = 1
        q = qubit.new(n_qubits)
        # apply U3 rotation that can be translated to a Clifford gate
        squin.qubit.apply(op.u(0.25 * math.tau, 0.0 * math.tau, 0.5 * math.tau), q[0])
        # S @ SQRT_Y @ S = Z @ SQRT_X
        squin.qubit.apply(
            op.u(-0.25 * math.tau, -0.25 * math.tau, -0.25 * math.tau), q[0]
        )
        # S @ SQRT_Y @ S_DAG = SQRT_X_DAG
        squin.qubit.apply(
            op.u(-0.25 * math.tau, -0.25 * math.tau, 0.25 * math.tau), q[0]
        )
        # S_DAG @ SQRT_Y @ S = SQRT_X
        squin.qubit.apply(
            op.u(-0.25 * math.tau, 0.25 * math.tau, -0.25 * math.tau), q[0]
        )

        # measure out
        squin.qubit.measure(q)
        return

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("u3_to_clifford.stim")

    assert codegen(test) == base_stim_prog.rstrip()


def test_sqrt_x_rewrite():

    @squin.kernel
    def test():
        q = qubit.new(1)
        qubit.broadcast(op.sqrt_x(), q)
        return

    SquinToStimPass(test.dialects)(test)

    assert codegen(test).strip() == "SQRT_X 0"


def test_sqrt_y_rewrite():

    @squin.kernel
    def test():
        q = qubit.new(1)
        qubit.broadcast(op.sqrt_y(), q)
        return

    SquinToStimPass(test.dialects)(test)

    assert codegen(test).strip() == "SQRT_Y 0"


def test_adjoint_gates_rewrite():

    @squin.kernel
    def test():
        q = qubit.new(4)
        s_adj = op.adjoint(op.s())
        qubit.apply(s_adj, q[0])
        sqrt_x_adj = op.adjoint(op.sqrt_x())
        qubit.apply(sqrt_x_adj, q[1])
        sqrt_y_adj = op.adjoint(op.sqrt_y())
        qubit.apply(sqrt_y_adj, q[2])
        sqrt_z_adj = op.adjoint(op.sqrt_z())  # same as S_DAG
        qubit.apply(sqrt_z_adj, q[3])
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test).strip() == "S_DAG 0\nSQRT_X_DAG 1\nSQRT_Y_DAG 2\nS_DAG 3"


def test_u3_rewrite():

    @squin.kernel
    def test():
        q = qubit.new(1)
        u3 = op.u(
            -math.pi / 2, -math.pi / 2, -math.pi / 2
        )  # S @ SQRT_Y @ S = SQRT_X_DAG @ Z
        qubit.apply(u3, q[0])
        u3 = op.u(
            -math.pi / 2, -math.pi / 2, math.pi / 2
        )  # S @ SQRT_Y @ S_DAG = SQRT_X_DAG
        qubit.apply(u3, q[0])
        u3 = op.u(
            -math.pi / 2, math.pi / 2, -math.pi / 2
        )  # S_DAG @ SQRT_Y @ S = SQRT_X
        qubit.apply(u3, q[0])

        return

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("u3_gates.stim")
    assert codegen(test) == base_stim_prog.rstrip()


def test_for_loop_nontrivial_index_rewrite():

    @squin.kernel
    def main():
        q = squin.qubit.new(3)
        squin.qubit.apply(squin.op.h(), q[0])
        cx = squin.op.cx()
        for i in range(2):
            squin.qubit.apply(cx, q[i], q[i + 1])

    SquinToStimPass(main.dialects)(main)
    base_stim_prog = load_reference_program("for_loop_nontrivial_index.stim")

    assert codegen(main) == base_stim_prog.rstrip()


def test_nested_for_loop_rewrite():

    @squin.kernel
    def main():
        q = squin.qubit.new(5)
        squin.qubit.apply(squin.op.h(), q[0])
        cx = squin.op.cx()
        for i in range(2):
            for j in range(2, 3):
                squin.qubit.apply(cx, q[i], q[j])

    SquinToStimPass(main.dialects)(main)
    base_stim_prog = load_reference_program("nested_for_loop.stim")

    assert codegen(main) == base_stim_prog.rstrip()


def test_nested_list():

    # NOTE: While SquinToStim now has the ability to handle
    # the nested list outside of the kernel in this test,
    # in general it will be necessary to explicitly
    # annotate it as an IList so type inference can work
    # properly. Otherwise its global, mutable nature means
    # we cannot assume a static type.

    pairs = [[0, 1], [2, 3]]

    @squin.kernel
    def main():
        q = qubit.new(10)
        h = squin.op.h()
        for i in range(2):
            squin.qubit.apply(h, q[pairs[i][0]])

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("nested_list.stim")

    assert codegen(main) == base_stim_prog.rstrip()


def test_pick_if_else():

    @squin.kernel
    def main():
        q = qubit.new(10)
        if False:
            qubit.apply(squin.op.h(), q[0])

        if True:
            qubit.apply(squin.op.h(), q[1])

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("pick_if_else.stim")

    assert codegen(main) == base_stim_prog.rstrip()


def test_non_pure_loop_iterator():
    @kernel
    def test_squin_kernel():
        q = qubit.new(5)
        result = qubit.measure(q)
        outputs = []
        for rnd in range(len(result)):  # Non-pure loop iterator
            outputs += []
            qubit.apply(op.x(), q[rnd])  # make sure body does something
        return

    main = test_squin_kernel.similar()
    SquinToStimPass(main.dialects)(main)
    base_stim_prog = load_reference_program("non_pure_loop_iterator.stim")
    assert codegen(main) == base_stim_prog.rstrip()
