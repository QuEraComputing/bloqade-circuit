import pytest

from bloqade import squin
from bloqade.types import Qubit
from bloqade.pyqrack import StackMemorySimulator


@pytest.mark.parametrize(
    "op_name",
    [
        "x",
        "y",
        "z",
        "sqrt_x",
        "sqrt_y",
        "sqrt_z",
        "sqrt_x_adj",
        "sqrt_y_adj",
        "sqrt_z_adj",
        "h",
        "s",
        "s_adj",
        "t",
        "t_adj",
        "p0",
        "p1",
        "spin_n",
        "spin_p",
        "reset",
    ],
)
def test_single_qubit_apply(op_name: str):
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        getattr(squin.gate, op_name)(q[0])

    main.print()

    sim = StackMemorySimulator(min_qubits=1)

    sim.run(main)


@pytest.mark.parametrize(
    "op_name",
    [
        "cx",
        "cy",
        "cz",
        "ch",
    ],
)
def test_control_apply(op_name: str):
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        getattr(squin.gate, op_name)(q[0], q[1])

    main.print()
    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)


@pytest.mark.parametrize(
    "op_name",
    [
        "x",
        "y",
        "z",
        "sqrt_x",
        "sqrt_y",
        "sqrt_z",
        "sqrt_x_adj",
        "sqrt_y_adj",
        "sqrt_z_adj",
        "h",
        "s",
        "s_adj",
        "t",
        "t_adj",
        "p0",
        "p1",
        "spin_n",
        "spin_p",
        "reset",
    ],
)
def test_single_qubit_broadcast(op_name: str):
    @squin.kernel
    def main():
        q = squin.qubit.new(4)
        getattr(squin.parallel, op_name)(q)

    main.print()

    sim = StackMemorySimulator(min_qubits=4)

    sim.run(main)


@pytest.mark.parametrize(
    "op_name",
    [
        "cx",
        "cy",
        "cz",
        "ch",
    ],
)
def test_control_broadcast(op_name: str):
    @squin.kernel
    def main():
        controls = squin.qubit.new(3)
        targets = squin.qubit.new(3)
        getattr(squin.parallel, op_name)(controls, targets)

    main.print()
    sim = StackMemorySimulator(min_qubits=6)
    sim.run(main)


def test_nested_kernel_inline():
    @squin.kernel
    def subkernel(q: Qubit):
        squin.gate.x(q)

    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        subkernel(q[0])

    main.print()
    sim = StackMemorySimulator(min_qubits=1)
    sim.run(main)


@pytest.mark.parametrize(
    "op_name",
    [
        "rx",
        "ry",
        "rz",
    ],
)
def test_parameter_gates(op_name: str):
    @squin.kernel
    def main():
        q = squin.qubit.new(4)
        theta = 0.123
        getattr(squin.gate, op_name)(theta, q[0])

        getattr(squin.parallel, op_name)(theta, q)

    main.print()

    sim = StackMemorySimulator(min_qubits=4)
    sim.run(main)


def test_phased_xz():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        squin.gate.phased_xz(
            x_exponent=0.5, z_exponent=0.5, axis_exponent=0.5, qubit=q[0]
        )

    main.print()

    sim = StackMemorySimulator(min_qubits=1)
    sim.run(main)
