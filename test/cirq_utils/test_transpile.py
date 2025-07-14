import cirq

from bloqade.cirq_utils import transpile


def test_transpile():
    def create_On_ghz_circuit(n):
        qubits = cirq.LineQubit.range(n)
        circuit = cirq.Circuit()

        # Step 1: Hadamard on the first qubit
        circuit.append(cirq.H(qubits[0]))

        # Step 2: CNOT chain from qubit i to i+1
        for i in range(n - 1):
            circuit.append(cirq.CNOT(qubits[i], qubits[i + 1]))

        return circuit

    circuit = create_On_ghz_circuit(4)

    native_circuit = transpile(circuit)

    print(native_circuit)

    assert native_circuit.moments[0].operations[0].gate.x_exponent == 0.5, print(
        native_circuit
    )
