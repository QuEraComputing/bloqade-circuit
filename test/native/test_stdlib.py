from typing import Any

import numpy as np
import pytest
from kirin import ir
from kirin.dialects import ilist

from bloqade import squin, native
from bloqade.pyqrack import DynamicMemorySimulator


def test_ghz():

    @native.kernel(typeinfer=True, fold=True)
    def main():
        qreg = squin.qalloc(4)

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
        (native.sqrt_y, [c, -c]),
        (native.sqrt_x_adj, [c, c * 1j]),
        (native.sqrt_y_adj, [c, c]),
        (native.s, [1.0, 0.0]),
        (native.s_dag, [1.0, 0.0]),
    ],
)
def test_1q_gate(gate_func: ir.Method, expected: Any):
    @native.kernel
    def main():
        q = squin.qalloc(1)
        gate_func(q[0])

    sv = DynamicMemorySimulator().state_vector(main)
    sv = np.asarray(sv)

    if abs(sv[0]) > 1e-10:
        sv /= sv[0] / np.abs(sv[0])
    else:
        sv /= sv[1] / np.abs(sv[1])

    print(sv, expected)
    assert np.allclose(sv, expected, atol=1e-6)


@pytest.mark.parametrize(
    "native_gate_func, squin_gate_func",
    [
        (native.cx, squin.cx),
        (native.cy, squin.cy),
        (native.cz, squin.cz),
    ],
)
def test_2q_gate_against_squin(native_gate_func: ir.Method, squin_gate_func: ir.Method):
    @native.kernel
    def main():
        q = squin.qalloc(2)
        native.x(q[0])
        native_gate_func(q[0], q[1])

    @squin.kernel
    def main_squin():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin_gate_func(q[0], q[1])

    sv_native = DynamicMemorySimulator().state_vector(main)
    sv_squin = DynamicMemorySimulator().state_vector(main_squin)

    sv_native = np.asarray(sv_native)
    sv_squin = np.asarray(sv_squin)

    native_i = np.abs(sv_native).argmax()
    sv_native *= np.exp(-1j * np.angle(sv_native[native_i]))

    squin_i = np.abs(sv_squin).argmax()
    sv_squin *= np.exp(-1j * np.angle(sv_squin[squin_i]))

    print(native_gate_func.sym_name, sv_native, sv_squin)
    assert np.allclose(sv_native, sv_squin, atol=1e-6)


@pytest.mark.parametrize(
    "native_gate_func, squin_gate_func",
    [
        (native.h, squin.h),
        (native.x, squin.x),
        (native.y, squin.y),
        (native.z, squin.z),
        (native.s, squin.s),
        (native.s_dag, squin.s_adj),
        (native.sqrt_x, squin.sqrt_x),
        (native.sqrt_x_adj, squin.sqrt_x_adj),
        (native.sqrt_y, squin.sqrt_y),
        (native.sqrt_y_adj, squin.sqrt_y_adj),
        (native.t, squin.t),
    ],
)
def test_1q_gate_against_squin(native_gate_func: ir.Method, squin_gate_func: ir.Method):
    @native.kernel
    def main():
        q = squin.qalloc(1)
        native_gate_func(q[0])

    @squin.kernel
    def main_squin():
        q = squin.qalloc(1)
        squin_gate_func(q[0])

    sv_native = DynamicMemorySimulator().state_vector(main)
    sv_squin = DynamicMemorySimulator().state_vector(main_squin)

    sv_native = np.asarray(sv_native)
    sv_squin = np.asarray(sv_squin)

    if abs(sv_native[0]) > 1e-10:
        sv_native *= np.exp(-1j * np.angle(sv_native[0]))
    else:
        sv_native *= np.exp(-1j * np.angle(sv_native[1]))

    if abs(sv_squin[0]) > 1e-10:
        sv_squin *= np.exp(-1j * np.angle(sv_squin[0]))
    else:
        sv_squin *= np.exp(-1j * np.angle(sv_squin[1]))

    print(native_gate_func.sym_name, sv_native, sv_squin)
    assert np.allclose(sv_native, sv_squin, atol=1e-6)
