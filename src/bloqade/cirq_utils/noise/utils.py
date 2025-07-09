import warnings
from typing import Tuple

import cirq
from cirq.circuits.qasm_output import QasmUGate

from .model import GeminiOneZoneNoiseModel
from ..parallelize import parallelize


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


def transform_to_noisy_one_zone_circuit(
    circuit: cirq.Circuit,
    to_target_gateset: bool = True,
    model: cirq.NoiseModel | None = None,
    parallelize_circuit: bool = False,
) -> Tuple[cirq.Circuit, cirq.Circuit]:
    """Transform and input circuit into a one with the native gateset with alternating 1Q and 2Q moments and add noise.

    @param circuit: Input circuit.
    @return:
        [0] Transformed circuit without noise.
        [1] Transformed circuit with noise.
    """

    if model is None:
        model = GeminiOneZoneNoiseModel()

    system_qubits = circuit.all_qubits()
    # Transform to CZ + PhasedXZ gateset.
    if to_target_gateset:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # TODO: parallelize does this optimization too;
            # check if we can skip this one here if parallelize is True
            native_circuit = cirq.optimize_for_target_gateset(
                circuit=circuit, gateset=cirq.CZTargetGateset()
            )
    else:
        native_circuit = circuit

    # Split into moments with only 1Q and 2Q gates
    moments_1q = [
        cirq.Moment([op for op in moment.operations if len(op.qubits) == 1])
        for moment in native_circuit.moments
    ]
    moments_2q = [
        cirq.Moment([op for op in moment.operations if len(op.qubits) == 2])
        for moment in native_circuit.moments
    ]

    assert len(moments_1q) == len(moments_2q)

    interleaved_moments = []
    for idx, moment in enumerate(moments_1q):
        interleaved_moments.append(moment)
        interleaved_moments.append(moments_2q[idx])

    interleaved_circuit = cirq.Circuit.from_moments(*interleaved_moments)

    # Combine subsequent 1Q gates
    compressed_circuit = cirq.merge_single_qubit_moments_to_phxz(interleaved_circuit)
    if parallelize_circuit:
        compressed_circuit = parallelize(compressed_circuit)
    compressed_circuit = (
        cirq.Circuit(
            cirq.PhasedXZGate(
                x_exponent=0, z_exponent=0, axis_phase_exponent=0
            ).on_each(system_qubits)
        )
        + compressed_circuit
    )
    # Add noise
    noisy_circuit = compressed_circuit.with_noise(model)

    return compressed_circuit[1:], noisy_circuit[2:]


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
