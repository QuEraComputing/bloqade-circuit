import io
import os
import math
from math import pi

import pytest
from kirin import ir
from kirin.dialects import py, scf

from bloqade import stim, qubit, squin as sq
from bloqade.squin import kernel
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass
from bloqade.rewrite.passes.aggressive_unroll import AggressiveUnroll


# Taken gratuitously from Kai's unit test
def codegen(mt: ir.Method):
    # method should not have any arguments!
    buf = io.StringIO()
    emit = EmitStimMain(dialects=stim.main, io=buf)
    emit.initialize()
    emit.run(mt)
    return buf.getvalue().strip()


def filter_statements_by_type(
    method: ir.Method, types: tuple[type, ...]
) -> list[ir.Statement]:
    return [
        stmt
        for stmt in method.callable_region.blocks[0].stmts
        if isinstance(stmt, types)
    ]


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
        ql = sq.qalloc(n_qubits)
        sq.broadcast.h(ql)
        sq.x(ql[0])
        sq.cx(ql[0], ql[1])
        sq.broadcast.measure(ql)
        return

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("qubit.stim")
    assert codegen(test) == base_stim_prog.rstrip()


def test_qubit_reset():
    @kernel
    def test():
        n_qubits = 1
        q = sq.qalloc(n_qubits)
        # reset the qubit
        qubit.broadcast.reset(q)
        # measure out
        sq.qubit.measure(q[0])
        return

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("qubit_reset.stim")

    assert codegen(test) == base_stim_prog.rstrip()


def test_qubit_broadcast():
    @kernel
    def test():
        n_qubits = 4
        ql = sq.qalloc(n_qubits)
        # apply Hadamard to all qubits
        sq.broadcast.h(ql)
        # measure out
        sq.broadcast.measure(ql)
        return

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("qubit_broadcast.stim")

    assert codegen(test) == base_stim_prog.rstrip()


def test_gates_with_loss():
    @kernel
    def test():
        n_qubits = 5
        ql = sq.qalloc(n_qubits)
        # apply Hadamard to all qubits
        sq.broadcast.h(ql)
        # apply and broadcast qubit loss
        sq.qubit_loss(p=0.1, qubit=ql[3])
        sq.broadcast.qubit_loss(p=0.05, qubits=ql)
        # measure out
        sq.broadcast.measure(ql)
        return

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("qubit_loss.stim")

    assert codegen(test) == base_stim_prog.rstrip()


def test_u3_to_clifford():

    @kernel
    def test():
        n_qubits = 1
        q = sq.qalloc(n_qubits)
        # apply U3 rotation that can be translated to a Clifford gate
        sq.u3(0.25 * math.tau, 0.0 * math.tau, 0.5 * math.tau, qubit=q[0])
        # measure out
        sq.broadcast.measure(q)
        return

    SquinToStimPass(test.dialects)(test)

    base_stim_prog = load_reference_program("u3_to_clifford.stim")

    assert codegen(test) == base_stim_prog.rstrip()


def test_sqrt_x_rewrite():

    @sq.kernel
    def test():
        q = sq.qalloc(1)
        sq.broadcast.sqrt_x(q)
        return

    SquinToStimPass(test.dialects)(test)

    assert codegen(test).strip() == "SQRT_X 0"


def test_sqrt_y_rewrite():

    @sq.kernel
    def test():
        q = sq.qalloc(1)
        sq.broadcast.sqrt_y(q)
        return

    SquinToStimPass(test.dialects)(test)

    assert codegen(test).strip() == "SQRT_Y 0"


def test_adjoint_gates_rewrite():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        sq.s_adj(q[0])
        sq.sqrt_x_adj(q[1])
        sq.sqrt_y_adj(q[2])
        sq.sqrt_z_adj(q[3])  # same as S_DAG
        return

    SquinToStimPass(test.dialects)(test)
    assert codegen(test).strip() == "S_DAG 0\nSQRT_X_DAG 1\nSQRT_Y_DAG 2\nS_DAG 3"


def test_u3_rewrite():

    @sq.kernel
    def test():
        q = sq.qalloc(1)

        sq.u3(-pi / 2, -pi / 2, -pi / 2, q[0])  # S @ SQRT_Y @ S = SQRT_X_DAG @ Z
        sq.u3(-pi / 2, -pi / 2, pi / 2, q[0])  # S @ SQRT_Y @ S_DAG = SQRT_X_DAG
        sq.u3(-pi / 2, pi / 2, -pi / 2, q[0])  # S_DAG @ SQRT_Y @ S = SQRT_X
        return

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("u3_gates.stim")
    assert codegen(test) == base_stim_prog.rstrip()


def test_for_loop_nontrivial_index_rewrite():

    @sq.kernel
    def main():
        q = sq.qalloc(3)
        sq.h(q[0])
        for i in range(2):
            sq.cx(q[i], q[i + 1])

    SquinToStimPass(main.dialects)(main)
    base_stim_prog = load_reference_program("for_loop_nontrivial_index.stim")

    assert codegen(main) == base_stim_prog.rstrip()


def test_nested_for_loop_rewrite():

    @sq.kernel
    def main():
        q = sq.qalloc(5)
        sq.h(q[0])
        for i in range(2):
            for j in range(2, 3):
                sq.cx(q[i], q[j])

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

    @sq.kernel
    def main():
        q = sq.qalloc(10)
        for i in range(2):
            sq.h(q[pairs[i][0]])

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("nested_list.stim")

    assert codegen(main) == base_stim_prog.rstrip()


def test_pick_if_else():

    @sq.kernel(fold=False)
    def main():
        q = sq.qalloc(10)
        if False:
            sq.h(q[0])

        if True:
            sq.h(q[1])

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("pick_if_else.stim")

    assert codegen(main) == base_stim_prog.rstrip()


def test_valid_if_measure_predicate():
    @sq.kernel
    def test():
        q = sq.qalloc(3)
        ms = sq.broadcast.measure(q)
        could_be_one = sq.broadcast.is_one(ms)
        sq.broadcast.reset(q)
        if could_be_one[0]:
            sq.x(q[0])

        if could_be_one[1]:
            sq.y(q[1])

        if could_be_one[2]:
            sq.z(q[2])

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("valid_if_measure_predicate.stim")
    assert codegen(test) == base_stim_prog.rstrip()


# You can only convert a combination of a predicate type and
# scf.IfElse if the predicate type is IS_ONE. Otherwise anything
# else is invalid
def test_invalid_if_measure_predicate():
    @sq.kernel
    def test():
        q = sq.qalloc(3)
        ms = sq.broadcast.measure(q)
        could_be_zero = sq.broadcast.is_zero(ms)
        could_be_lost = sq.broadcast.is_lost(ms)
        sq.broadcast.reset(q)

        if could_be_zero[0]:
            sq.x(q[0])

        if could_be_lost[1]:
            sq.y(q[1])

    SquinToStimPass(test.dialects)(test)
    # rewrite for scf.IfElse did not occur due to invalid predicate type,
    # should have two scf.IfElse remaining
    remaining_if_else = filter_statements_by_type(test, (scf.IfElse,))
    assert len(remaining_if_else) == 2


test_invalid_if_measure_predicate()


def test_non_pure_loop_iterator():
    @kernel
    def test_squin_kernel():
        q = sq.qalloc(5)
        result = qubit.broadcast.measure(q)
        outputs = []
        for rnd in range(len(result)):  # Non-pure loop iterator
            outputs += []
            sq.x(q[rnd])  # make sure body does something

    main = test_squin_kernel.similar()
    AggressiveUnroll(main.dialects).fixpoint(main)

    SquinToStimPass(main.dialects, no_raise=False)(main)
    base_stim_prog = load_reference_program("non_pure_loop_iterator.stim")
    assert codegen(main) == base_stim_prog.rstrip()


def test_rep_code():

    # NOTE: This is not a true repetition code in the sense there is no
    # detector definition or final observables being defined.

    @sq.kernel
    def entangle(cx_pairs):
        sq.broadcast.cx(controls=cx_pairs[0][0], targets=cx_pairs[0][1])
        sq.broadcast.cx(controls=cx_pairs[1][0], targets=cx_pairs[1][1])

    @sq.kernel
    def rep_code():

        q = sq.qalloc(5)
        data = q[::2]
        ancilla = q[1::2]

        # reset everything initially
        qubit.broadcast.reset(q)

        ## Initial round, entangle data qubits with ancillas.
        ## This entanglement will happen again so it's best we
        ## save the qubit pairs for reuse.
        cx_pair_1_controls = [data[0], data[1]]
        cx_pair_1_targets = [ancilla[0], ancilla[1]]
        cx_pair_1 = [cx_pair_1_controls, cx_pair_1_targets]

        cx_pair_2_controls = [data[1], data[2]]
        cx_pair_2_targets = [ancilla[0], ancilla[1]]
        cx_pair_2 = [cx_pair_2_controls, cx_pair_2_targets]

        cx_pairs = [cx_pair_1, cx_pair_2]

        entangle(cx_pairs)

        qubit.broadcast.measure(ancilla)

        entangle(cx_pairs)
        qubit.broadcast.measure(ancilla)

        # Let's make this one a bit noisy
        entangle(cx_pairs)
        sq.broadcast.depolarize2(
            0.01, controls=cx_pair_1_controls, targets=cx_pair_1_targets
        )
        sq.broadcast.qubit_loss(p=0.001, qubits=q)

        qubit.broadcast.measure(ancilla)

    SquinToStimPass(rep_code.dialects)(rep_code)
    base_stim_prog = load_reference_program("rep_code.stim")
    assert codegen(rep_code) == base_stim_prog.rstrip()


@pytest.mark.parametrize(
    "angle,expected",
    [
        (0, ""),
        (pi / 2, "S 0"),
        (pi, "Z 0"),
        (3 * pi / 2, "S_DAG 0"),
        (-pi / 2, "S_DAG 0"),
    ],
    ids=["0", "pi/2", "pi", "3pi/2", "-pi/2"],
)
def test_rz_to_clifford(angle, expected):
    @kernel
    def test():
        q = sq.qalloc(1)
        sq.rz(angle, q[0])

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == expected


@pytest.mark.parametrize(
    "angle,expected",
    [
        (0, ""),
        (pi / 2, "SQRT_X 0"),
        (pi, "X 0"),
        (3 * pi / 2, "SQRT_X_DAG 0"),
        (-pi / 2, "SQRT_X_DAG 0"),
    ],
    ids=["0", "pi/2", "pi", "3pi/2", "-pi/2"],
)
def test_rx_to_clifford(angle, expected):
    @kernel
    def test():
        q = sq.qalloc(1)
        sq.rx(angle, q[0])

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == expected


@pytest.mark.parametrize(
    "angle,expected",
    [
        (0, ""),
        (pi / 2, "SQRT_Y 0"),  # Ry(π/2) = √Y
        (pi, "Y 0"),
        (3 * pi / 2, "SQRT_Y_DAG 0"),
        (-pi / 2, "SQRT_Y_DAG 0"),
    ],
    ids=["0", "pi/2", "pi", "3pi/2", "-pi/2"],
)
def test_ry_to_clifford(angle, expected):
    @kernel
    def test():
        q = sq.qalloc(1)
        sq.ry(angle, q[0])

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == expected


@pytest.mark.parametrize(
    "gate_func,angle,expected",
    [
        (sq.rz, pi / 2 + 1e-12, "S 0"),  # Near π/2
        (sq.rx, pi / 2 - 1e-12, "SQRT_X 0"),  # Near π/2
        (sq.ry, pi + 1e-12, "Y 0"),  # Near π
    ],
    ids=["rz_near_pi/2", "rx_near_pi/2", "ry_near_pi"],
)
def test_rotation_near_clifford_angles(gate_func, angle, expected):
    @kernel
    def test():
        q = sq.qalloc(1)
        gate_func(angle, q[0])

    SquinToStimPass(test.dialects)(test)
    assert codegen(test) == expected
