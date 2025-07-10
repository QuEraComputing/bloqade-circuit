import cirq

from bloqade.cirq_utils.noise import (
    GeminiTwoZoneNoiseModel,
    transform_circuit,
    transform_circuit_v1,
    get_two_zoned_noisy_circ,
)

'''In the v1 workflow, interleaving is not done inside transform_circuit_v1. Rather transform circuit_v1 uses the
GeminiOneZoneNoiseModel_v1 class, which does in interleaving inside it's noisy_moments method.
'''

def create_ghz_circuit(n):
    qubits = cirq.LineQubit.range(n)
    circuit = cirq.Circuit()

    # Step 1: Hadamard on the first qubit
    circuit.append(cirq.H(qubits[0]))

    # Step 2: CNOT chain from qubit i to i+1
    for i in range(n - 1):
        circuit.append(cirq.CNOT(qubits[i], qubits[i + 1]))

    return circuit

assert transform_circuit(create_ghz_circuit(5))[1] == transform_circuit_v1(create_ghz_circuit(5))
print(transform_circuit(create_ghz_circuit(5))[1] == transform_circuit_v1(create_ghz_circuit(5)))