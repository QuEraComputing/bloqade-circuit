from typing import Any

import numpy as np
import pytest
from kirin import ir
from kirin.dialects import ilist

from bloqade import native
from bloqade.squin import qubit
from bloqade.pyqrack import DynamicMemorySimulator


def test_ghz():

    @native.kernel(typeinfer=True, fold=True)
    def main():
        qreg = qubit.new(4)

        native.h(qreg[0])

        prepped_qubits = ilist.IList([qreg[0]])
        for i in range(1, len(qreg)):
            unset_qubits = qreg[len(prepped_qubits) :]
            ctrls = ilist.IList([])
            qargs = ilist.IList([])
            for j in range(len(prepped_qubits)):
                if j < len(unset_qubits):
                    ctrls = ctrls + ilist.IList([prepped_qubits[j]])
                    qargs = qargs + ilist.IList([unset_qubits[j]])

            if len(ctrls) > 0:
                native.broadcast.cx(ctrls, qargs)
                prepped_qubits = prepped_qubits + qargs

    sv = DynamicMemorySimulator().state_vector(main)
    sv = np.asarray(sv)
    sv /= sv[0] / np.abs(sv[0])

    expected = np.zeros_like(sv)
    expected[0] = 1.0 / np.sqrt(2.0)
    expected[-1] = 1.0 / np.sqrt(2.0)

    assert np.allclose(sv, expected, atol=1e-6)


@pytest.mark.parametrize(
    "gate_func, expected",
    [
        (native.x, [0.0, 1.0]),
        (native.y, [0.0, 1.0]),
        (native.h, [c := 1 / np.sqrt(2.0), c]),
        (native.sqrt_x, [c, -c * 1j]),
        (native.sqrt_y, [c, c]),
        (native.sqrt_x_adj, [c, c * 1j]),
        (native.sqrt_y_adj, [c, -c]),
        (native.s, [1.0, 0.0]),
        (native.s_dag, [1.0, 0.0]),
    ],
)
def test_1q_gate(gate_func: ir.Method[[qubit.Qubit], None], expected: Any):
    @native.kernel
    def main():
        q = qubit.new(1)
        gate_func(q[0])

    sv = DynamicMemorySimulator().state_vector(main)
    sv = np.asarray(sv)

    if abs(sv[0]) > 1e-10:
        sv /= sv[0] / np.abs(sv[0])
    else:
        sv /= sv[1] / np.abs(sv[1])

    print(sv, expected)
    assert np.allclose(sv, expected, atol=1e-6)
