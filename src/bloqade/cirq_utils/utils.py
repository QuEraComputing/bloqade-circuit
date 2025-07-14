import cirq
from cirq.circuits.qasm_output import QasmUGate


def transform_to_qasm_u_gates(circuit: cirq.Circuit) -> cirq.Circuit:
    """
    Transforms all single-qubit gates in a Cirq circuit into QasmUGates.

    Args:
        circuit: A cirq.Circuit object.

    Returns:
        A new cirq.Circuit object where all single-qubit gates are replaced with QasmUGates.
    """
    new_circuit = cirq.Circuit()

    for moment in circuit:
        new_moment = []
        for op in moment.operations:
            if len(op.qubits) == 1:  # Check if it's a single-qubit gate
                qubit = op.qubits[0]
                gate = op.gate

                # Decompose the gate into QasmUGate parameters (theta, phi, lambda)
                if isinstance(gate, cirq.Gate):
                    u_gate = QasmUGate.from_matrix(cirq.unitary(gate))
                    new_moment.append(u_gate.on(qubit))
                else:
                    # If the gate cannot be converted, keep it as is
                    new_moment.append(op)
            else:
                # Keep multi-qubit gates as is
                new_moment.append(op)

        new_circuit.append(cirq.Moment(new_moment))

    return new_circuit
