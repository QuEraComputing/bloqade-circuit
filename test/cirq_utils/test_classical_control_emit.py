from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch

import cirq
import pytest
from kirin import ir, interp
from kirin.dialects import scf, ilist
from kirin.validation import ValidationSuite
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.qubit import stmts as qubit_stmts
from bloqade.squin import gate as squin_gate
from bloqade.cirq_utils import emit_circuit, classical_control as cc
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.cirq_utils.emit.scf import __EmitCirqScfMethods
from bloqade.cirq_utils.emit.base import EmitCirq
from bloqade.cirq_utils.emit.qubit import EmitCirqQubitMethods
from bloqade.cirq_utils.validation import (
    CirqClassicalControlValidation,
    classical_control as validation_module,
)
from bloqade.cirq_utils.validation.classical_control import (
    _ScfMethods,
    _CirqClassicalControlValidationAnalysis,
)


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
    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
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

    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
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

    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
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

    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
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

    AggressiveUnroll(main.dialects).fixpoint(main)
    result = ValidationSuite([CirqClassicalControlValidation]).validate(main)
    assert result.error_count() == 1
    assert any(
        "non-empty else body" in message
        for message in [
            str(err.args[0]) for errors in result.errors.values() for err in errors
        ]
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

    AggressiveUnroll(main.dialects).fixpoint(main)
    result = ValidationSuite([CirqClassicalControlValidation]).validate(main)
    assert result.error_count() == 1
    assert any(
        "exactly one gate operation" in message
        for message in [
            str(err.args[0]) for errors in result.errors.values() for err in errors
        ]
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

    AggressiveUnroll(main.dialects).fixpoint(main)
    result = ValidationSuite([CirqClassicalControlValidation]).validate(main)
    assert result.error_count() == 1
    assert any(
        "must compare a single measurement result" in message
        for message in [
            str(err.args[0]) for errors in result.errors.values() for err in errors
        ]
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

    AggressiveUnroll(main.dialects).fixpoint(main)
    result = ValidationSuite([CirqClassicalControlValidation]).validate(main)
    assert result.error_count() >= 1
    assert any(
        "Nested IfElse statements" in message
        for message in [
            str(err.args[0]) for errors in result.errors.values() for err in errors
        ]
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
    ifelse = next(
        stmt for stmt in main.callable_region.walk() if isinstance(stmt, scf.IfElse)
    )
    condition = cc.parse_classical_if_condition(ifelse.cond)
    assert condition is not None

    measure = Mock()
    measure.qubits = Mock()
    measure.qubits.type = int
    condition = cc.ClassicalIfCondition(measure=measure, trigger_on_one=False)
    assert cc.is_single_qubit_measure(measure) is False

    with patch.object(
        validation_module,
        "parse_classical_if_condition",
        return_value=condition,
    ):
        result = ValidationSuite([CirqClassicalControlValidation]).validate(main)

    assert result.error_count() == 1
    assert any(
        "single qubit measurement" in message
        for message in [
            str(err.args[0]) for errors in result.errors.values() for err in errors
        ]
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

    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
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

    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
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

    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
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

    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
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

    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
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

    AggressiveUnroll(main.dialects).fixpoint(main)
    result = ValidationSuite([CirqClassicalControlValidation]).validate(main)
    assert result.error_count() == 1
    assert any(
        "is_lost has no Cirq equivalent" in message
        for message in [
            str(err.args[0]) for errors in result.errors.values() for err in errors
        ]
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

    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
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

    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
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
    ifelse = next(
        stmt for stmt in main.callable_region.walk() if isinstance(stmt, scf.IfElse)
    )

    assert cc.is_empty_else(ifelse) is True
    assert cc.get_single_gate(ifelse) is not None
    assert cc.parse_classical_if_condition(ifelse.cond) is not None


def test_emit_if_reversed_eq():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if 0 == m:
            squin.x(q[0])

    circuit = emit_circuit(main)

    (controlled,) = [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]
    (condition,) = controlled.classical_controls
    assert isinstance(condition, cirq.BitMaskKeyCondition)
    assert condition.target_value == 0


def test_validation_rejects_invalid_neq_comparison():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m != 2:
            squin.x(q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    result = ValidationSuite([CirqClassicalControlValidation]).validate(main)
    assert result.error_count() == 1
    assert any(
        "must compare a single measurement result" in message
        for message in [
            str(err.args[0]) for errors in result.errors.values() for err in errors
        ]
    )


def test_classical_control_internal_helpers_return_none():
    assert cc._unwrap_constant(Mock()) is None
    assert cc._resolve_measure_stmt(Mock()) is None
    assert cc._resolve_predicate_chain(Mock()) is None


def test_is_empty_else_without_else_blocks():
    stmt = Mock(spec=scf.IfElse)
    stmt.else_body.blocks = []
    assert cc.is_empty_else(stmt) is True


def test_get_single_gate_edge_cases():
    stmt = Mock(spec=scf.IfElse)
    stmt.then_body.blocks = []
    assert cc.get_single_gate(stmt) is None

    block = Mock()
    block.stmts = [Mock()]
    stmt.then_body.blocks = [block]
    assert cc.get_single_gate(stmt) is None

    yield_stmt = Mock(spec=scf.Yield)
    yield_stmt.values = [Mock()]
    gate_stmt = Mock(spec=squin_gate.stmts.Gate)
    block.stmts = [gate_stmt, yield_stmt]
    assert cc.get_single_gate(stmt) is None


def test_get_single_gate_rejects_qalloc_in_then():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 0:
            q2 = squin.qalloc(1)
            squin.x(q2[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    ifelse = next(
        stmt for stmt in main.callable_region.walk() if isinstance(stmt, scf.IfElse)
    )
    assert cc.get_single_gate(ifelse) is None


def test_emit_if_else_missing_measurement_key():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 0:
            squin.x(q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    ifelse = next(
        stmt for stmt in main.callable_region.walk() if isinstance(stmt, scf.IfElse)
    )
    emit = EmitCirq()
    frame = emit.initialize_frame(ifelse)
    table = __EmitCirqScfMethods()

    with pytest.raises(
        interp.exceptions.InterpreterError,
        match="missing measurement key",
    ):
        table.if_else(emit, frame, ifelse)


def test_measure_emit_uses_key_name_when_not_str():
    emit = EmitCirq()
    frame = Mock()
    stmt = Mock()
    stmt.qubits = Mock()
    stmt.result = Mock(spec=ir.SSAValue)
    frame.get.return_value = [cirq.LineQubit(0)]
    meas_op = MagicMock()
    meas_op.gate.key = SimpleNamespace(name="custom_key")
    with patch(
        "bloqade.cirq_utils.emit.qubit.cirq.measure",
        return_value=meas_op,
    ):
        EmitCirqQubitMethods().measure_qubit_list(emit, frame, stmt)
    assert emit.measurement_keys[stmt.result] == "custom_key"


def test_resolve_measure_stmt_through_ilist_new_from_kernel():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if squin.is_one(m)[0]:
            squin.x(q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    assert any(
        isinstance(cc._resolve_measure_stmt(stmt.result), qubit_stmts.Measure)
        for stmt in main.callable_region.walk()
        if isinstance(stmt, ilist.New)
    )


def test_parse_invalid_eq_comparison_returns_none():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 2:
            squin.x(q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    assert (
        cc.parse_classical_if_condition(
            next(
                stmt
                for stmt in main.callable_region.walk()
                if isinstance(stmt, scf.IfElse)
            ).cond
        )
        is None
    )


def test_emit_is_lost_handler():
    emit = EmitCirq()
    frame = Mock()
    stmt = Mock()
    assert EmitCirqQubitMethods().is_lost(emit, frame, stmt) == (emit.void,)


def test_emit_is_lost_is_no_op():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        squin.is_lost(m)

    emit_circuit(main)


def test_validation_skips_ifelse_when_walk_includes_self():
    from itertools import chain

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 0:
            squin.x(q[0])

    AggressiveUnroll(main.dialects).fixpoint(main)
    ifelse = next(
        stmt for stmt in main.callable_region.walk() if isinstance(stmt, scf.IfElse)
    )
    real_walk = ifelse.then_body.walk

    analysis = _CirqClassicalControlValidationAnalysis(main.dialects)
    frame = Mock()
    with patch.object(
        ifelse.then_body,
        "walk",
        return_value=chain([ifelse], real_walk()),
    ):
        _ScfMethods().if_else(analysis, frame, ifelse)
    assert analysis.get_validation_errors() == []


def test_emit_reset():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.reset(q[0])

    circuit = emit_circuit(main)
    assert any(
        isinstance(op.gate, cirq.ResetChannel) for op in circuit.all_operations()
    )
