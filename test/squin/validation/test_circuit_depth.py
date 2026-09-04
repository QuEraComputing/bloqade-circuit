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
