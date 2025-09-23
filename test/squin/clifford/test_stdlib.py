import math
from typing import Any

import numpy as np
import pytest
from kirin import ir

from bloqade import squin
from bloqade.types import Qubit
from bloqade.pyqrack import StackMemorySimulator, DynamicMemorySimulator


def test_ghz():
    n = 4

    @squin.kernel
    def main():
        q = squin.qubit.new(n)
        squin.h(q[0])

        for i in range(n - 1):
            squin.cx(q[i], q[i + 1])

    main.print()

    sim = StackMemorySimulator(min_qubits=n)
    ket = sim.state_vector(main)

    print(abs(ket[0]) ** 2)

    assert math.isclose(abs(ket[0]) ** 2, 0.5, abs_tol=1e-4)
    assert math.isclose(abs(ket[-1] ** 2), 0.5, abs_tol=1e-4)
    for k in ket[1:-1]:
        assert k == 0


@pytest.mark.parametrize(
    "gate_func, expected",
    [
        (squin.x, [0.0, 1.0]),
        (squin.y, [0.0, 1.0]),
        (squin.h, [c := 1 / math.sqrt(2.0), c]),
        (squin.sqrt_x, [c, -c * 1j]),
        (squin.sqrt_y, [c, -c]),
        (squin.sqrt_x_adj, [c, c * 1j]),
        (squin.sqrt_y_adj, [c, c]),
        (squin.s, [1.0, 0.0]),
        (squin.s_adj, [1.0, 0.0]),
    ],
)
def test_1q_gate(gate_func: ir.Method[[Qubit], None], expected: Any):
    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        gate_func(q[0])

    sv = DynamicMemorySimulator().state_vector(main)
    sv = np.asarray(sv)

    if abs(sv[0]) > 1e-10:
        sv /= sv[0] / np.abs(sv[0])
    else:
        sv /= sv[1] / np.abs(sv[1])

    print(sv, expected)
    assert np.allclose(sv, expected, atol=1e-6)
