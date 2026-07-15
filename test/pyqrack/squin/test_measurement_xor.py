from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator, MeasurementResultValue


def test_measurement_xor_parity():
    @squin.kernel
    def one_xor_zero():
        q = squin.qalloc(2)
        squin.x(q[0])
        return squin.measure(q[0]) ^ squin.measure(q[1])

    @squin.kernel
    def one_xor_one():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.x(q[1])
        return squin.measure(q[0]) ^ squin.measure(q[1])

    sim = StackMemorySimulator(min_qubits=2)
    assert sim.run(one_xor_zero) is MeasurementResultValue.One
    assert sim.run(one_xor_one) is MeasurementResultValue.Zero


def test_measurement_xor_with_loss_is_lost():
    @squin.kernel
    def xor_after_loss():
        q = squin.qalloc(2)
        squin.qubit_loss(1.0, q[0])
        return squin.measure(q[0]) ^ squin.measure(q[1])

    sim = StackMemorySimulator(
        min_qubits=2,
        loss_m_result=MeasurementResultValue.Lost,
    )
    assert sim.run(xor_after_loss) is MeasurementResultValue.Lost
