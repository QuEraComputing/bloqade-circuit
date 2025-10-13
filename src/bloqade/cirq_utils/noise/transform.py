import cirq

from .model import GeminiOneZoneNoiseModel
from ..parallelize import transpile, parallelize


def transform_circuit(
    circuit: cirq.Circuit,
    to_native_gateset: bool = True,
    model: cirq.NoiseModel | None = None,
    parallelize_circuit: bool = False,
) -> cirq.Circuit:
    """Transform an input circuit into one with the native gateset with noise operations added.

    Noise operations will be added to all qubits in circuit.all_qubits(), regardless of whether the output of the
    circuit optimizers contain all the qubits.

    Args:
        circuit (cirq.Circuit): The input circuit.

    Keyword Arguments:
        to_native_gateset (bool): Whether or not to convert the input circuit to one using the native set of gates (`cirq.CZTargetGateset`)
            only. Defaults to `True`. Note, that if you use an input circuit that has gates different from this gateset and don't convert it,
            may lead to incorrect results and errors.
        model (cirq.NoiseModel): The cirq noise model to apply to the circuit. Usually, you want to use one of the ones supplied in this submodule,
            such as `GeminiOneZoneNoiseModel`.
        parallelize_circuit (bool): Whether or not to parallelize the circuit as much as possible after it's been converted to the native gateset.
            Defaults to `False`.

    Returns:
        cirq.Circuit:
            The resulting noisy circuit.
    """
    if model is None:
        model = GeminiOneZoneNoiseModel(parallelize_circuit=parallelize_circuit)

    # only parallelize here if we aren't parallelizing inside a one-zone model
    parallelize_circuit_here = parallelize_circuit and not isinstance(
        model, GeminiOneZoneNoiseModel
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
