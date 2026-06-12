from unittest.mock import Mock

import cirq
import pytest
from kirin import ir
from kirin.dialects import scf
from kirin.validation import ValidationSuite
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.cirq_utils import emit_circuit, classical_control as cc
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.analysis.validation.cirq_classical_control import (
    CirqClassicalControlValidation,
    validation as validation_module,
)


def _controlled_ops(circuit: cirq.Circuit) -> list[cirq.ClassicallyControlledOperation]:
    return [
        op
        for moment in circuit
        for op in moment.operations
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]


def _unroll_and_validate(main: ir.Method):
    AggressiveUnroll(main.dialects).fixpoint(main)
    suite = ValidationSuite([CirqClassicalControlValidation])
    return suite.validate(main)


def _find_ifelse(main: ir.Method) -> scf.IfElse:
    for stmt in main.callable_region.walk():
        if isinstance(stmt, scf.IfElse):
            return stmt
    raise AssertionError("expected IfElse in kernel")


def _validation_messages(result) -> list[str]:
    messages: list[str] = []
    for errors in result.errors.values():
        for validation_error in errors:
            messages.append(str(validation_error.args[0]))
    return messages


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

    result = _unroll_and_validate(main)
    assert result.error_count() == 1
    assert any(
        "non-empty else body" in message for message in _validation_messages(result)
    )

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

    result = _unroll_and_validate(main)
    assert result.error_count() == 1
    assert any(
        "exactly one gate operation" in message
        for message in _validation_messages(result)
    )

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_validation_rejects_invalid_condition():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m:
            squin.x(q[0])

    result = _unroll_and_validate(main)
    assert result.error_count() == 1
    assert any(
        "must compare a single measurement result" in message
        for message in _validation_messages(result)
    )

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_validation_rejects_nested_if():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 0:
            if m == 1:
                squin.x(q[0])

    result = _unroll_and_validate(main)
    assert result.error_count() >= 1
    assert any(
        "Nested IfElse statements" in message for message in _validation_messages(result)
    )

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_validation_rejects_multi_qubit_measure():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 0:
            squin.x(q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    ifelse = _find_ifelse(main)
    condition = cc.parse_classical_if_condition(ifelse.cond)
    assert condition is not None

    measure = Mock()
    measure.qubits = Mock()
    measure.qubits.type = int
    condition = cc.ClassicalIfCondition(measure=measure, trigger_on_one=False)
    assert cc.is_single_qubit_measure(measure) is False

    original_parse = validation_module.parse_classical_if_condition

    def patched_parse(_cond):
        return condition

    validation_module.parse_classical_if_condition = patched_parse
    try:
        result = ValidationSuite([CirqClassicalControlValidation]).validate(main)
    finally:
        validation_module.parse_classical_if_condition = original_parse

    assert result.error_count() == 1
    assert any(
        "single qubit measurement" in message for message in _validation_messages(result)
    )

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


def test_emit_if_measurement_neq_zero():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m != 0:
            squin.x(q[0])

    circuit = emit_circuit(main)

    (controlled,) = _controlled_ops(circuit)
    (condition,) = controlled.classical_controls
    assert isinstance(condition, cirq.BitMaskKeyCondition)
    assert condition.target_value == 1


def test_emit_if_measurement_neq_one():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m != 1:
            squin.x(q[0])

    circuit = emit_circuit(main)

    (controlled,) = _controlled_ops(circuit)
    (condition,) = controlled.classical_controls
    assert isinstance(condition, cirq.BitMaskKeyCondition)
    assert condition.target_value == 0


def test_emit_if_is_one():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if squin.is_one(m)[0]:
            squin.x(q[0])

    circuit = emit_circuit(main)

    (controlled,) = _controlled_ops(circuit)
    (condition,) = controlled.classical_controls
    assert isinstance(condition, cirq.BitMaskKeyCondition)
    assert condition.target_value == 1


def test_emit_if_is_zero():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if squin.is_zero(m)[0]:
            squin.x(q[0])

    circuit = emit_circuit(main)

    (controlled,) = _controlled_ops(circuit)
    (condition,) = controlled.classical_controls
    assert isinstance(condition, cirq.BitMaskKeyCondition)
    assert condition.target_value == 0


def test_validation_rejects_is_lost_condition():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if squin.is_lost(m)[0]:
            squin.x(q[0])

    result = _unroll_and_validate(main)
    assert result.error_count() == 1
    assert any(
        "is_lost has no Cirq equivalent" in message
        for message in _validation_messages(result)
    )

    with pytest.raises(ValidationErrorGroup):
        result.raise_if_invalid()


def test_emit_if_reversed_neq():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if 0 != m:
            squin.x(q[0])

    circuit = emit_circuit(main)

    (controlled,) = _controlled_ops(circuit)
    (condition,) = controlled.classical_controls
    assert isinstance(condition, cirq.BitMaskKeyCondition)
    assert condition.target_value == 1


def test_emit_if_with_custom_qubits():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 1:
            squin.x(q[0])

    qubits = [cirq.GridQubit(0, 0)]
    circuit = emit_circuit(main, circuit_qubits=qubits)

    (controlled,) = _controlled_ops(circuit)
    assert controlled.qubits == (cirq.GridQubit(0, 0),)


def test_classical_control_helpers_reject_non_result_values():
    assert cc.parse_classical_if_condition(Mock()) is None
    assert cc.is_is_lost_condition(Mock()) is False


def test_classical_control_helpers_on_kernel_ifelse():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 0:
            squin.x(q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    ifelse = _find_ifelse(main)

    assert cc.is_empty_else(ifelse) is True
    assert cc.get_single_gate(ifelse) is not None
    assert cc.parse_classical_if_condition(ifelse.cond) is not None
