import cirq
import pytest

from bloqade.cirq_utils import transpile


# NOTE: this test fails on Github runners, but passes locally
# the issue is that cirq somehow produces a circuit with a different PhXZ gate x_exponent
# depending on the hardware; need to do some more digging here
# also, not sure which version is actually correct
@pytest.mark.xfail
def test_transpile():
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.H(q[0]), cirq.CX(q[0], q[1]))

    native_circuit = transpile(circuit)

    print(native_circuit)

    assert native_circuit.moments[0].operations[0].gate.x_exponent == 0.5, print(
        native_circuit
    )
