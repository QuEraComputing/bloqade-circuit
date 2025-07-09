import cirq

from bloqade.cirq_utils.noise import (
    TwoZoneNoiseModel,
    transform_circuit,
    get_two_zoned_noisy_circ,
)


def create_ghz_circuit(n):
    qubits = cirq.LineQubit.range(n)
    circuit = cirq.Circuit()

    # Step 1: Hadamard on the first qubit
    circuit.append(cirq.H(qubits[0]))

    # Step 2: CNOT chain from qubit i to i+1
    for i in range(n - 1):
        circuit.append(cirq.CNOT(qubits[i], qubits[i + 1]))

    return circuit


model = TwoZoneNoiseModel()

circuit = create_ghz_circuit(2)

circuit_ = cirq.optimize_for_target_gateset(circuit, gateset=cirq.CZTargetGateset())
print(circuit_)
noisy_circuit = get_two_zoned_noisy_circ(circuit_)

print(noisy_circuit)

compressed_circuit_from_model, noisy_circuit_from_model = transform_circuit(
    circuit, model=model
)

print(compressed_circuit_from_model)
print(noisy_circuit_from_model)
