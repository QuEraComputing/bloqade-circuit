import pytest
from kirin.passes import inline

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
        q = squin.qubit.new(1)
        p = 0.1
        getattr(squin.channel, op_name)(p, q[0])

    main.print()

    # NOTE: need to inline invokes so the noise rewrite can do its thing
    inline.InlinePass(main.dialects)(main)

    sim = StackMemorySimulator(min_qubits=1)
    sim.run(main)


def test_pauli_error():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        p = 0.1
        x = squin.op.x()
        squin.channel.pauli_error(x, p, q[0])

    main.print()

    # NOTE: need to inline invokes so the noise rewrite can do its thing
    inline.InlinePass(main.dialects)(main)

    sim = StackMemorySimulator(min_qubits=1)
    sim.run(main)


def test_single_qubit_pauli_channel():
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        px = 0.1
        py = 0.1
        pz = 0.05
        squin.channel.single_qubit_pauli_channel([px, py, pz], q[0])

    main.print()

    # NOTE: need to inline invokes so the noise rewrite can do its thing
    inline.InlinePass(main.dialects)(main)

    sim = StackMemorySimulator(min_qubits=1)
    sim.run(main)


def test_depolarize2():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        p = 0.1
        squin.channel.depolarize2(p, q[0], q[1])

    main.print()

    # NOTE: need to inline invokes so the noise rewrite can do its thing
    inline.InlinePass(main.dialects)(main)

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)


def test_two_qubit_pauli_channel():
    @squin.kernel
    def main():
        q = squin.qubit.new(2)

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

        squin.channel.two_qubit_pauli_channel(ps, q[0], q[1])

    main.print()

    # NOTE: need to inline invokes so the noise rewrite can do its thing
    inline.InlinePass(main.dialects)(main)

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)
