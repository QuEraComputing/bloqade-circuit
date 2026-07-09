import pytest
from kirin.lowering import BuildError
from kirin.ir.exception import ValidationError

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


def test_two_qubit_pauli_channel_shorthand_local_lists():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        paulis = ["XX", "YY", "ZZ"]
        probs = [0.1, 0.2, 0.15]
        squin.two_qubit_pauli_channel(paulis, probs, q[0], q[1])

    output = main.print_str()
    assert "IList([0.0, 0.0, 0.0, 0.0, 0.1" in output
    assert "0.2, 0.0, 0.0, 0.0, 0.0, 0.15])" in output

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)


def test_two_qubit_pauli_channel_shorthand_literal_lists():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.two_qubit_pauli_channel(["XX", "ZZ"], [0.1, 0.15], q[0], q[1])

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)


def test_two_qubit_pauli_channel_broadcast_shorthand():
    @squin.kernel
    def main():
        controls = squin.qalloc(2)
        targets = squin.qalloc(2)
        squin.broadcast.two_qubit_pauli_channel(
            ["XX", "ZZ"], [0.1, 0.15], controls, targets
        )

    main.print()

    sim = StackMemorySimulator(min_qubits=4)
    sim.run(main)


def test_two_qubit_pauli_channel_broadcast_full_signature():
    @squin.kernel
    def main():
        controls = squin.qalloc(2)
        targets = squin.qalloc(2)
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
        squin.broadcast.two_qubit_pauli_channel(ps, controls, targets)

    main.print()

    sim = StackMemorySimulator(min_qubits=4)
    sim.run(main)


def test_two_qubit_pauli_channel_broadcast_rejects_static_length_mismatch():
    with pytest.raises(ValidationError, match="same length"):

        @squin.kernel
        def main():
            q = squin.qalloc(3)
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
            squin.broadcast.two_qubit_pauli_channel(ps, [q[0], q[1]], [q[2]])


def test_two_qubit_pauli_channel_shorthand_rejects_runtime_lists():
    with pytest.raises(BuildError, match="statically known"):

        @squin.kernel
        def main(paulis: list[str], probs: list[float]):
            q = squin.qalloc(2)
            squin.two_qubit_pauli_channel(paulis, probs, q[0], q[1])


def test_two_qubit_pauli_channel_shorthand_rejects_unknown_pauli():
    with pytest.raises(BuildError, match="Invalid two-qubit Pauli product"):

        @squin.kernel
        def main():
            q = squin.qalloc(2)
            squin.two_qubit_pauli_channel(["AA"], [0.1], q[0], q[1])
