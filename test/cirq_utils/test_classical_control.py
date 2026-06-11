import cirq
import pytest
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.cirq_utils import emit_circuit


def test_emit_measurement_equal_one_as_classical_control():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        m = squin.measure(q[0])
        if m == 1:
            squin.x(q[1])

    circuit = emit_circuit(main)
    ops = list(circuit.all_operations())

    assert len(ops) == 2
    assert ops[0] == cirq.measure(cirq.LineQubit(0))
    assert isinstance(ops[1], cirq.ClassicallyControlledOperation)
    assert ops[1].sub_operation == cirq.X(cirq.LineQubit(1))


def test_emit_measurement_equal_zero_as_classical_control():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        m = squin.measure(q[0])
        if m == 0:
            squin.x(q[1])

    circuit = emit_circuit(main)
    ops = list(circuit.all_operations())

    assert len(ops) == 2
    assert isinstance(ops[1], cirq.ClassicallyControlledOperation)
    assert ops[1].sub_operation == cirq.X(cirq.LineQubit(1))


def test_rejects_non_empty_else_body():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        m = squin.measure(q[0])
        if m == 1:
            squin.x(q[1])
        else:
            squin.z(q[1])

    with pytest.raises(ValidationErrorGroup, match="else body"):
        emit_circuit(main)


def test_rejects_multiple_then_body_gates():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        m = squin.measure(q[0])
        if m == 1:
            squin.x(q[1])
            squin.z(q[1])

    with pytest.raises(ValidationErrorGroup, match="exactly one gate"):
        emit_circuit(main)
