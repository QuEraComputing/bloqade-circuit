import cirq
import pytest
from kirin.ir.exception import ValidationErrorGroup
from kirin.validation import ValidationSuite

from bloqade import squin
from bloqade.analysis.validation.cirq_classical_control import (
    CirqClassicalControlValidation,
)
from bloqade.cirq_utils import emit_circuit


def _controlled_ops(circuit: cirq.Circuit) -> list[cirq.ClassicallyControlledOperation]:
    return [
        op
        for moment in circuit
        for op in moment.operations
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]


def test_emit_if_measurement_eq_zero():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.h(q[0])
        m = squin.measure(q[0])
        if m == 0:
            squin.x(q[0])

    circuit = emit_circuit(main)

    assert len(circuit) == 3
    assert any(cirq.is_measurement(op) for op in circuit.all_operations())
    (controlled,) = _controlled_ops(circuit)
    assert controlled.without_classical_controls().gate == cirq.X
    (condition,) = controlled.classical_controls
    assert isinstance(condition, cirq.BitMaskKeyCondition)
    assert condition.target_value == 0


def test_emit_if_measurement_eq_one():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.h(q[0])
        m = squin.measure(q[0])
        if m == 1:
            squin.x(q[0])

    circuit = emit_circuit(main)

    (controlled,) = _controlled_ops(circuit)
    assert controlled.without_classical_controls().gate == cirq.X
    (condition,) = controlled.classical_controls
    assert isinstance(condition, cirq.BitMaskKeyCondition)
    assert condition.target_value == 1


def test_emit_if_measurement_eq_true():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == True:  # noqa: E712
            squin.x(q[0])

    circuit = emit_circuit(main)

    (controlled,) = _controlled_ops(circuit)
    (condition,) = controlled.classical_controls
    assert isinstance(condition, cirq.BitMaskKeyCondition)
    assert condition.target_value == 1


def test_emit_if_measurement_eq_false():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == False:  # noqa: E712
            squin.x(q[0])

    circuit = emit_circuit(main)

    (controlled,) = _controlled_ops(circuit)
    (condition,) = controlled.classical_controls
    assert isinstance(condition, cirq.BitMaskKeyCondition)
    assert condition.target_value == 0


def test_validation_rejects_non_empty_else():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 0:
            squin.x(q[0])
        else:
            squin.z(q[0])

    suite = ValidationSuite([CirqClassicalControlValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_validation_rejects_multiple_gates_in_then():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 0:
            squin.x(q[0])
            squin.z(q[0])

    suite = ValidationSuite([CirqClassicalControlValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_validation_rejects_invalid_condition():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m:
            squin.x(q[0])

    suite = ValidationSuite([CirqClassicalControlValidation])
    result = suite.validate(main)
    assert result.error_count() == 1

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_emit_circuit_raises_on_invalid_if():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m:
            squin.x(q[0])

    with pytest.raises(ValidationErrorGroup):
        emit_circuit(main)


def test_kernels_without_if_still_emit():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])

    circuit = emit_circuit(main)
    assert len(circuit) == 2


def test_emit_if_cx():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        m = squin.measure(q[0])
        if m == 1:
            squin.cx(q[0], q[1])

    circuit = emit_circuit(main)

    (controlled,) = _controlled_ops(circuit)
    assert controlled.without_classical_controls().gate == cirq.CNOT
    (condition,) = controlled.classical_controls
    assert isinstance(condition, cirq.BitMaskKeyCondition)
    assert condition.target_value == 1
