from bloqade import squin
from bloqade.squin.analysis.validation.circuit_depth import (
    FlatKernelCircuitDepthValidation,
)


def test_errors_when_circuit_exceeds_single_qubit_threshold():
    @squin.kernel
    def too_deep():
        q = squin.qalloc(1)
        squin.x(q[0])
        squin.h(q[0])
        squin.z(q[0])

    _, errors = FlatKernelCircuitDepthValidation(
        single_qubit_gate_threshold=1,
        two_qubit_gate_threshold=100,
    ).run(too_deep)

    assert errors
    assert any("too deep" in str(err).lower() for err in errors)


def test_errors_when_circuit_exceeds_two_qubit_threshold():
    @squin.kernel
    def too_deep():
        q = squin.qalloc(2)
        squin.cz(q[0], q[1])
        squin.cx(q[0], q[1])

    _, errors = FlatKernelCircuitDepthValidation(
        single_qubit_gate_threshold=100,
        two_qubit_gate_threshold=1,
    ).run(too_deep)

    assert len(errors) == 1
    assert "two-qubit gates" in str(errors[0])


def test_errors_when_both_thresholds_are_exceeded():
    @squin.kernel
    def too_deep():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.cz(q[0], q[1])

    _, errors = FlatKernelCircuitDepthValidation(
        single_qubit_gate_threshold=0,
        two_qubit_gate_threshold=0,
    ).run(too_deep)

    assert len(errors) == 2
    messages = [str(error) for error in errors]
    assert any("single-qubit gates" in message for message in messages)
    assert any("two-qubit gates" in message for message in messages)
