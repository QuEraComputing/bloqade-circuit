import cirq

from bloqade.pyqrack import MeasurementResultValue
from bloqade import squin
from bloqade.cirq_utils import emit_circuit
from bloqade.pyqrack import StackMemorySimulator


@squin.kernel
def annotated_kernel():
    q = squin.qalloc(2)
    squin.x(q[1])
    m = squin.broadcast.measure(q)
    squin.set_detector([m[0]], coordinates=(0, 0))
    squin.set_observable([m[0]])
    return m[1]


def test_cirq_emitter_ignores_annotations():
    circuit = emit_circuit(annotated_kernel, ignore_returns=True)
    q = cirq.LineQubit.range(2)

    assert circuit == cirq.Circuit(cirq.X(q[1]), cirq.measure(*q))


def test_pyqrack_simulator_ignores_annotations():
    result = StackMemorySimulator(min_qubits=2).run(annotated_kernel)

    assert result == MeasurementResultValue.One
