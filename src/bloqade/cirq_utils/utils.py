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


# TODO: this kind of duplicates parallelize.transpile; try to unify?
def optimize_circuit_to_cz_gate_set(circuit: cirq.Circuit) -> cirq.Circuit:
    """
    Optimizes a Cirq circuit to reduce the number of gates while keeping it in the CZ gate set.

    Args:
        circuit: A cirq.Circuit object.

    Returns:
        An optimized cirq.Circuit object.
    """
    # Step 1: Decompose all gates into CZ and single-qubit gates
    decomposed_circuit = cirq.expand_composite(circuit)

    # Step 2: Merge single-qubit gates into PhasedXZGate (U3-like gate)
    decomposed_circuit = cirq.merge_single_qubit_gates_to_phased_x_and_z(
        decomposed_circuit
    )

    # Step 3: Drop empty moments
    decomposed_circuit = cirq.drop_empty_moments(decomposed_circuit)

    # Step 4: Optimize for the CZ gate set
    optimized_circuit = cirq.optimize_for_target_gateset(
        decomposed_circuit, gateset=cirq.CZTargetGateset()
    )

    return optimized_circuit
