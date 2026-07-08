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
    ],
)
def test_single_qubit_apply(op_name: str):
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        getattr(squin, op_name)(q[0])

    main.print()

    sim = StackMemorySimulator(min_qubits=1)

    sim.run(main)


@pytest.mark.parametrize(
    "op_name",
    [
        "cx",
        "cy",
        "cz",
        "swap",
    ],
)
def test_control_apply(op_name: str):
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        getattr(squin, op_name)(q[0], q[1])

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
    ],
)
def test_single_qubit_broadcast(op_name: str):
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        getattr(squin.broadcast, op_name)(q)

    main.print()

    sim = StackMemorySimulator(min_qubits=4)

    sim.run(main)


@pytest.mark.parametrize(
    "op_name",
    [
        "cx",
        "cy",
        "cz",
        "swap",
    ],
)
def test_control_broadcast(op_name: str):
    @squin.kernel
    def main():
        controls = squin.qalloc(3)
        targets = squin.qalloc(3)
        getattr(squin.broadcast, op_name)(controls, targets)

    main.print()
    sim = StackMemorySimulator(min_qubits=6)
    sim.run(main)


def test_nested_kernel_inline():
    @squin.kernel
    def subkernel(q: Qubit):
        squin.x(q)

    @squin.kernel
    def main():
        q = squin.qalloc(1)
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
        q = squin.qalloc(4)
        theta = 0.123
        getattr(squin, op_name)(theta, q[0])

        getattr(squin.broadcast, op_name)(theta, q)

    main.print()

    sim = StackMemorySimulator(min_qubits=4)
    sim.run(main)


@pytest.mark.parametrize(
    "op_name",
    [
        "depolarize",
        "qubit_loss",
    ],
)
def test_single_qubit_noise(op_name: str):
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        p = 0.1
        getattr(squin, op_name)(p, q[0])

    main.print()

    sim = StackMemorySimulator(min_qubits=1)
    sim.run(main)


def test_single_qubit_pauli_channel():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        px = 0.1
        py = 0.1
        pz = 0.05
        squin.single_qubit_pauli_channel(px, py, pz, q[0])

    main.print()

    sim = StackMemorySimulator(min_qubits=1)
    sim.run(main)


def test_depolarize2():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        p = 0.1
        squin.depolarize2(p, q[0], q[1])

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)


def test_two_qubit_pauli_channel():
    @squin.kernel
    def main():
        q = squin.qalloc(2)

        # NOTE: this API is not great
        ps = [
            0.0001,
            0.0001,
            0.0001,
            0.0001,
            0.0001,
            0.0001,
            0.0001,
            0.0001,
            0.0001,
            0.0001,
            0.0001,
            0.0001,
            0.0001,
            0.0001,
            0.0001,
        ]

        squin.two_qubit_pauli_channel(ps, q[0], q[1])

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)


def test_two_qubit_pauli_channel_shorthand():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        probabilities = [("XX", 0.0001), ("YY", 0.0001), ("ZZ", 0.0001)]
        squin.two_qubit_pauli_channel_shorthand(probabilities, q[0], q[1])

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)


def test_two_qubit_pauli_channel_shorthand_duplicate_pauli_string_runs():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        probabilities = [("XX", 0.0001), ("XX", 0.0002)]
        squin.two_qubit_pauli_channel_shorthand(probabilities, q[0], q[1])

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)


def test_two_qubit_pauli_channel_shorthand_more_than_fifteen_entries_runs():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        probabilities = [
            ("IX", 0.0001),
            ("IY", 0.0001),
            ("IZ", 0.0001),
            ("XI", 0.0001),
            ("XX", 0.0001),
            ("XY", 0.0001),
            ("XZ", 0.0001),
            ("YI", 0.0001),
            ("YX", 0.0001),
            ("YY", 0.0001),
            ("YZ", 0.0001),
            ("ZI", 0.0001),
            ("ZX", 0.0001),
            ("ZY", 0.0001),
            ("ZZ", 0.0001),
            ("XX", 0.0001),
        ]
        squin.two_qubit_pauli_channel_shorthand(probabilities, q[0], q[1])

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)


def test_two_qubit_pauli_channel_shorthand_unknown_pauli_string_runs():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        probabilities = [("AB", 0.0001), ("XX", 0.0001)]
        squin.two_qubit_pauli_channel_shorthand(probabilities, q[0], q[1])

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)


def test_two_qubit_pauli_channel_shorthand_negative_probability_lowers():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        probabilities = [("XX", -0.0001)]
        squin.two_qubit_pauli_channel_shorthand(probabilities, q[0], q[1])

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    with pytest.raises(AssertionError, match="Invalid Pauli error probabilities"):
        sim.run(main)
