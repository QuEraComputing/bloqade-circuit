import math
import typing

import cirq
import pytest
from kirin.emit import EmitError
from kirin.dialects import ilist

from bloqade import squin
from bloqade.cirq_utils import emit, emit_circuit


def test_pauli():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        q2 = squin.qalloc(4)

        squin.x(q[0])
        squin.y(q2[0])
        squin.z(q2[3])

    circuit = emit_circuit(main)

    print(circuit)

    qbits = circuit.all_qubits()
    assert len(qbits) == 3
    assert isinstance(qbit := list(qbits)[-1], cirq.LineQubit)
    assert qbit.x == 5

if __name__ == "__main__":
    test_pauli()


@pytest.mark.parametrize("op_name", ["h", "s", "t", "x", "y", "z"])
def test_basic_op(op_name: str):
    @squin.kernel
    def main():
        q =squin.qalloc(1)
        getattr(squin, op_name)(q)

    emit_circuit(main)


def test_control():
    @squin.kernel
    def main():
        q =squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])

    circuit = emit_circuit(main)

    print(circuit)

    assert len(circuit) == 2
    assert circuit[1].operations[0].gate == cirq.CNOT


def test_custom_qubits():
    @squin.kernel
    def main():
        q =squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])

    qubits = [cirq.GridQubit(0, 1), cirq.GridQubit(2, 2)]
    circuit = emit_circuit(main, qubits=qubits)

    print(circuit)

    circuit_qubits = circuit.all_qubits()
    assert len(circuit_qubits) == 2
    assert frozenset(qubits) == circuit_qubits


def test_composed_kernels():
    @squin.kernel
    def sub_kernel(q_: ilist.IList[squin.qubit.Qubit, typing.Any]):
        squin.h(q_[0])

    @squin.kernel
    def main():
        q =squin.qalloc(2)
        sub_kernel(q)

    circuit = emit_circuit(main)

    print(circuit)

    assert len(circuit) == 1
    assert len(circuit[0].operations) == 1
    assert isinstance(circuit[0].operations[0], cirq.GateOperation)


def test_nested_kernels():
    @squin.kernel
    def sub_kernel2(q2_: ilist.IList[squin.qubit.Qubit, typing.Any]):
        squin.cx(q2_[0], q2_[1])

    @squin.kernel
    def sub_kernel(q_: ilist.IList[squin.qubit.Qubit, typing.Any]):
        squin.h(q_[0])
        sub_kernel2(q_)

    @squin.kernel
    def main():
        q =squin.qalloc(2)
        sub_kernel(q)

    circuit = emit_circuit(main)

    print(circuit)


def test_return_value():
    @squin.kernel
    def sub_kernel():
        q =squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        return q

    @squin.kernel
    def main():
        q = sub_kernel()
        squin.h(q[0])

    circuit = emit_circuit(main)

    print(circuit)

    with pytest.raises(EmitError):
        emit_circuit(sub_kernel)

    @squin.kernel
    def main2():
        q = sub_kernel()
        squin.h(q[0])
        return q

    circuit2 = emit_circuit(main2, ignore_returns=True)
    print(circuit2)

    assert circuit2 == circuit


def test_return_qubits():
    @squin.kernel
    def sub_kernel(q: ilist.IList[squin.qubit.Qubit, typing.Any]):
        squin.h(q[0])
        q2 =squin.qalloc(3)
        squin.cx(q[0], q2[2])
        return q2

    @squin.kernel
    def main():
        q =squin.qalloc(2)
        q2_ = sub_kernel(q)
        squin.x(q2_[0])

    circuit = emit_circuit(main)

    print(circuit)


def test_measurement():
    @squin.kernel
    def main():
        q =squin.qalloc(2)
        squin.broadcast.y(q)
        squin.qubit.measure(q)

    circuit = emit_circuit(main)

    print(circuit)


def test_adjoint():
    @squin.kernel
    def main():
        q =squin.qalloc(1)
        squin.s(q[0])
        squin.s_adj(q[0])

    circuit = emit_circuit(main)
    print(circuit)


def test_u3():
    @squin.kernel
    def main():
        q =squin.qalloc(1)
        squin.u3(0.323, 1.123, math.pi / 7, q[0])

    circuit = emit_circuit(main)
    print(circuit)


def test_shift():
    @squin.kernel
    def main():
        q =squin.qalloc(1)
        squin.shift(math.pi / 7, q[0])

    circuit = emit_circuit(main)
    print(circuit)


def test_invoke_cache():
    @squin.kernel
    def sub_kernel(q_: squin.qubit.Qubit):
        squin.h(q_)

    @squin.kernel
    def main():
        q =squin.qalloc(2)
        q0 = q[0]
        sub_kernel(q0)
        sub_kernel(q[1])
        sub_kernel(q0)

    target = emit.base.EmitCirq(main.dialects)

    circuit = target.run(main, ())

    print(circuit)

    # caches as well as squin.h and squin.broadcast.h with the different qubits
    assert len(target._cached_invokes) == 6


def test_rot():
    @squin.kernel
    def main():
        q =squin.qalloc(1)
        squin.rx(math.pi / 2, q[0])

    circuit = emit_circuit(main)

    print(circuit)

    assert circuit[0].operations[0].gate == cirq.Rx(rads=math.pi / 2)


def test_additional_stmts():
    @squin.kernel
    def main():
        q =squin.qalloc(3)
        squin.rot(math.pi / 4, math.pi / 2, -math.pi / 4, q[0])
        squin.sqrt_x(q[1])
        squin.sqrt_y(q[2])

    main.print()

    circuit = emit_circuit(main)

    print(circuit)

    q = cirq.LineQubit.range(3)
    expected_circuit = cirq.Circuit(
        cirq.Rz(rads=math.pi / 4).on(q[0]),
        cirq.Ry(rads=math.pi / 2).on(q[0]),
        cirq.Rz(rads=-math.pi / 4).on(q[0]),
        cirq.X(q[1]) ** 0.5,
        cirq.Y(q[2]) ** 0.5,
    )

    assert circuit == expected_circuit


def test_return_measurement():

    @squin.kernel
    def coinflip():
        qubit =squin.qalloc(1)[0]
        squin.h(qubit)
        return squin.qubit.measure(qubit)

    coinflip.print()

    circuit = emit_circuit(coinflip, ignore_returns=True)
    print(circuit)
