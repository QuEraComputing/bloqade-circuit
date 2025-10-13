import math

from kirin import ir
from kirin.dialects import func

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator


def get_return_value_stmt(kernel: ir.Method):
    assert isinstance(
        last_stmt := kernel.callable_region.blocks[-1].last_stmt, func.Return
    )
    return last_stmt.value.owner


def test_measure_register():
    @squin.kernel
    def test_measure_sugar():
        q = squin.qubit.new(2)

        return squin.qubit.measure(q)

    assert isinstance(
        get_return_value_stmt(test_measure_sugar), squin.qubit.MeasureQubitList
    )


def test_measure_qubit():
    @squin.kernel
    def test_measure_sugar():
        q = squin.qubit.new(2)

        return squin.qubit.measure(q[0])

    assert isinstance(
        get_return_value_stmt(test_measure_sugar),
        squin.qubit.MeasureQubit,
    )


def test_apply_sugar():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        h = squin.op.h()
        x = squin.op.x()

        # test applying to list with getindex
        squin.qubit.apply(x, [q[0]])

        # test apply with ast.Name
        q0 = q[0]
        squin.qubit.apply(x, q0)
        squin.qubit.apply(x, [q0])

        squin.qubit.apply(h, q[0])

        # test vararg and whole register
        cx = squin.op.cx()
        squin.qubit.apply(cx, q)
        squin.qubit.apply(cx, q0, q[1])
        return q

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    ket = sim.state_vector(main)

    assert math.isclose(abs(ket[0]) ** 2, 0.5, abs_tol=1e-5)
    assert math.isclose(abs(ket[1]) ** 2, 0.5, abs_tol=1e-5)
    assert ket[2] == ket[3] == 0


def test_apply_in_for_loop():

    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        x = squin.op.x()
        for i in range(2):
            squin.qubit.apply(x, q[i])
            squin.qubit.apply(x, [q[i]])

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    ket = sim.state_vector(main)

    assert math.isclose(abs(ket[0]) ** 2, 1, abs_tol=1e-4)
    assert ket[1] == ket[2] == ket[3] == 0


def test_apply_in_for_loop_index_multiple_index():

    @squin.kernel
    def main():
        q = squin.qubit.new(3)
        squin.qubit.apply(squin.op.h(), q[0])
        cx = squin.op.cx()
        for i in range(2):
            squin.qubit.apply(cx, q[i], q[i + 1])

    sim = StackMemorySimulator(min_qubits=3)
    ket = sim.state_vector(main)
    assert math.isclose(abs(ket[0]) ** 2, 0.5, abs_tol=1e-5)


def test_apply_with_named_args():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        h = squin.op.h()
        squin.qubit.apply(h, qubits=[q[0]])
        cx = squin.op.cx()
        squin.qubit.apply(qubits=q, operator=cx)

    main.print()


def test_new_apply_syntax():

    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        squin.qubit.apply(x, q[0])

    main.verify()

    @squin.kernel
    def ghz():
        controls = squin.qubit.new(4)
        targets = squin.qubit.new(4)

        h = squin.op.h()
        for i in range(4):
            squin.qubit.apply(h, controls[i])

        cx = squin.op.cx()
        for i in range(4):
            squin.qubit.apply(cx, controls[i], targets[i])

    ghz.print()

    ghz.verify()


def test_new_broadcast_syntax():
    @squin.kernel
    def main():
        controls = squin.qubit.new(4)
        targets = squin.qubit.new(4)

        h = squin.op.h()
        squin.qubit.broadcast(h, controls)

        cx = squin.op.cx()
        squin.qubit.broadcast(cx, controls, targets)

    main.print()
