import pytest

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator


@pytest.mark.parametrize(
    "op_name",
    [
        "x",
        "y",
        "z",
        # "sqrt_x",  # NOTE: missing pyqrack methods
        # "sqrt_y",
        "sqrt_z",
        "h",
        "s",
        "t",
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
