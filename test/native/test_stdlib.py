from typing import Any

import numpy as np
import pytest
from kirin import ir
from kirin.dialects import ilist

from bloqade.squin import qubit
from bloqade.native import kernel, stdlib
from bloqade.pyqrack import DynamicMemorySimulator


def test_ghz():

    @kernel
    def main():
        qreg = qubit.new(10)

        stdlib.h(qreg[0])

        prepped_qubits = [qreg[0]]
        for i in range(1, len(qreg)):
            unset_qubits = qreg[len(prepped_qubits) :]
            ctrls = ilist.IList([])
            qargs = ilist.IList([])
            for j in range(len(prepped_qubits)):
                if j < len(unset_qubits):
                    ctrls = ctrls + [prepped_qubits[j]]
                    qargs = qargs + [unset_qubits[j]]

            if len(ctrls) > 0:
                stdlib.broadcast.cz(ctrls, qargs)
                prepped_qubits = prepped_qubits + qargs

    sv = DynamicMemorySimulator().state_vector(main)
    expected = np.zeros_like(sv)
    expected[0] = 1.0 / np.sqrt(2.0)
    expected[-1] = 1.0 / np.sqrt(2.0)

    assert np.abs(np.vdot(sv, expected)) - 1 < 1e-6


@pytest.mark.parametrize(
    "gate_func, expected",
    [
        (stdlib.x, [0.0, 1.0]),
        (stdlib.y, [0.0, 1.0]),
        (stdlib.h, [np.sqrt(0.5), np.sqrt(0.5)]),
        (stdlib.sqrt_x, [np.sqrt(0.5), np.sqrt(0.5)]),
        (stdlib.sqrt_y, [np.sqrt(0.5), np.sqrt(0.5)]),
        (stdlib.sqrt_x_dag, [np.sqrt(0.5), np.sqrt(0.5)]),
        (stdlib.sqrt_y_dag, [np.sqrt(0.5), np.sqrt(0.5)]),
        (stdlib.s, [0.0, 1.0]),
        (stdlib.s_dag, [0.0, 1.0]),
    ],
)
def test_1q_gate(gate_func: ir.Method[[qubit.Qubit], None], expected: Any):
    @kernel
    def main():
        q = qubit.new(1)
        gate_func(q[0])

    sv = DynamicMemorySimulator().state_vector(main)
    assert np.abs(np.vdot(sv, expected)) - 1 < 1e-6
