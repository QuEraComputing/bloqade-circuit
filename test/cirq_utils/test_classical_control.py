"""Tests for emitting measurement-conditioned squin if-statements as Cirq
classical controls (issue #408)."""

import cirq
import pytest
from kirin.interp.exceptions import InterpreterError

from bloqade import squin
from bloqade.cirq_utils import emit_circuit, load_circuit


def _controlled_ops(circuit: cirq.Circuit) -> list[cirq.ClassicallyControlledOperation]:
    return [
        op
        for op in circuit.all_operations()
        if isinstance(op, cirq.ClassicallyControlledOperation)
    ]


def _condition_strs(op: cirq.ClassicallyControlledOperation) -> list[str]:
    return [str(c) for c in op.classical_controls]


def test_emit_is_one_as_key_condition():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.h(q[0])
        m = squin.measure(q[0])
        if squin.is_one(m):
            squin.x(q[0])

    circuit = emit_circuit(main)
    controlled = _controlled_ops(circuit)
    assert len(controlled) == 1
    op = controlled[0]
    # fires on |1>: a bare KeyCondition on the measurement key
    assert _condition_strs(op) == ["q(0)"]
    assert isinstance(op.without_classical_controls(), cirq.GateOperation)
    assert op.without_classical_controls().gate == cirq.X


def test_emit_is_zero_as_sympy_condition():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if squin.is_zero(m):
            squin.x(q[0])

    circuit = emit_circuit(main)
    controlled = _controlled_ops(circuit)
    assert len(controlled) == 1
    # fires on |0>: Eq(key, 0)
    assert _condition_strs(controlled[0]) == ["Eq(q(0), 0)"]


def test_emit_eq_zero_comparison():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 0:
            squin.x(q[0])

    controlled = _controlled_ops(emit_circuit(main))
    assert len(controlled) == 1
    assert _condition_strs(controlled[0]) == ["Eq(q(0), 0)"]


def test_emit_eq_one_comparison():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m == 1:
            squin.x(q[0])

    controlled = _controlled_ops(emit_circuit(main))
    assert len(controlled) == 1
    assert _condition_strs(controlled[0]) == ["q(0)"]


def test_round_trip_classical_control():
    """A Cirq classical control survives cirq -> squin -> cirq."""
    q0, q1 = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.H(q0),
        cirq.measure(q0, key="a"),
        cirq.X(q1).with_classical_controls("a"),
    )
    mt = load_circuit(circuit)
    out = emit_circuit(mt)
    controlled = _controlled_ops(out)
    assert len(controlled) == 1
    # the imported control is preserved: an X classically controlled on q0's measurement
    op = controlled[0]
    assert op.without_classical_controls().gate == cirq.X
    assert len(op.classical_controls) == 1


def test_feed_forward_semantics():
    """if is_one(m): X(other)  flips the target exactly when the control fired."""

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.x(q[0])  # q0 := |1>
        m = squin.measure(q[0])
        if squin.is_one(m):  # always true here
            squin.x(q[1])  # so q1 becomes |1>
        squin.measure(q[1])

    circuit = emit_circuit(main)
    result = cirq.Simulator().run(circuit, repetitions=64)
    target_key = "q(1)"
    assert (result.measurements[target_key] == 1).all()


def test_no_if_is_unchanged():
    """Kernels without if-statements are unaffected."""

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])

    circuit = emit_circuit(main)
    assert _controlled_ops(circuit) == []


def test_error_multiple_gates_in_body():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if squin.is_one(m):
            squin.x(q[0])
            squin.y(q[0])

    with pytest.raises(InterpreterError, match="exactly one gate"):
        emit_circuit(main)


def test_error_non_empty_else():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if squin.is_one(m):
            squin.x(q[0])
        else:
            squin.y(q[0])

    with pytest.raises(InterpreterError, match="else body"):
        emit_circuit(main)


def test_error_is_lost_condition():
    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if squin.is_lost(m):
            squin.x(q[0])

    with pytest.raises(InterpreterError, match="is_lost"):
        emit_circuit(main)


def test_error_allocation_in_body():
    """The qubit-allocation-in-then-body shape (the bug that closed PR #790)."""

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if squin.is_one(m):
            r = squin.qalloc(1)
            squin.x(r[0])

    with pytest.raises(InterpreterError, match="unsupported statement"):
        emit_circuit(main)
