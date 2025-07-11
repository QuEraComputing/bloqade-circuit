# TODO: cirq is an extension, need an if here
import cirq

from .model import (
    GeminiOneZoneNoiseModel as GeminiOneZoneNoiseModel,
    GeminiTwoZoneNoiseModel as GeminiTwoZoneNoiseModel,
    GeminiOneZoneNoiseModelABC as GeminiOneZoneNoiseModelABC,
    GeminiOneZoneNoiseModelCorrelated as GeminiOneZoneNoiseModelCorrelated,
    GeminiOneZoneNoiseModelConflictGraphMoves as GeminiOneZoneNoiseModelConflictGraphMoves,
)
from .utils import (
    transform_to_qasm_u_gates as transform_to_qasm_u_gates,
    optimize_circuit_to_cz_gate_set as optimize_circuit_to_cz_gate_set,
    transform_to_noisy_one_zone_circuit as transform_to_noisy_one_zone_circuit,
)
from ..parallelize import transpile as transpile, parallelize
from .conflict_graph import OneZoneConflictGraph as OneZoneConflictGraph
from .two_zone_utils import (
    get_two_zoned_noisy_circ as get_two_zoned_noisy_circ,
)


def transform_circuit(
    circuit: cirq.Circuit,
    to_native_gateset: bool = True,
    model: cirq.NoiseModel | None = None,
    parallelize_circuit: bool = False,
) -> cirq.Circuit:
    """Transform and input circuit into a one with the native gateset with alternating 1Q and 2Q moments and add noise.

    Noise operations will be added to all qubits in circuit.all_qubits(), regardless of whether the output of the
    circuit optimizers contain all the qubits.

    TODO: args & stuff
    """
    if model is None:
        model = GeminiOneZoneNoiseModel(parallelize_circuit=parallelize_circuit)

    # only parallelize here if we aren't parallelizing inside a one-zone model
    parallelize_circuit_here = parallelize_circuit and not isinstance(
        model, GeminiOneZoneNoiseModelABC
    )

    system_qubits = sorted(circuit.all_qubits())
    # Transform to CZ + PhasedXZ gateset.
    if to_native_gateset and not parallelize_circuit_here:
        native_circuit = transpile(circuit)
    elif parallelize_circuit_here:
        native_circuit = parallelize(circuit)
    else:
        native_circuit = circuit

    # Add noise
    noisy_circuit = cirq.Circuit()
    for op_tree in model.noisy_moments(native_circuit, system_qubits):
        # Keep moments aligned
        noisy_circuit += cirq.Circuit(op_tree)

    return noisy_circuit
