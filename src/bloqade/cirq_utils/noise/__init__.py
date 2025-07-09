import warnings
from typing import Tuple

import cirq

from .model import (
    TwoRowZoneModel as TwoRowZoneModel,
    GeminiOneZoneNoiseModel as GeminiOneZoneNoiseModel,
    GeminiOneZoneNoiseModelCorrelated as GeminiOneZoneNoiseModelCorrelated,
    GeminiOneZoneNoiseModelConflictGraphMoves as GeminiOneZoneNoiseModelConflictGraphMoves,
)
from .utils import (
    transform_to_qasm_u_gates as transform_to_qasm_u_gates,
    optimize_circuit_to_cz_gate_set as optimize_circuit_to_cz_gate_set,
    transform_to_noisy_one_zone_circuit as transform_to_noisy_one_zone_circuit,
)
from ..parallelize import parallelize
from .conflict_graph import OneZoneConflictGraph as OneZoneConflictGraph
from .two_zone_model import (
    GeminiTwoZoneNoiseModel as GeminiTwoZoneNoiseModel,
    get_two_zoned_noisy_circ as get_two_zoned_noisy_circ,
)


def transform_circuit(
    circuit: cirq.Circuit,
    to_target_gateset: bool = True,
    model: cirq.NoiseModel = GeminiOneZoneNoiseModel(),
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
