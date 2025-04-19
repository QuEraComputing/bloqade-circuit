import math

import pytest
from kirin import ir

from bloqade import qasm2
from bloqade.pyqrack import PyQrack, reg


def test_target():

    @qasm2.main
    def ghz():
        q = qasm2.qreg(3)

        qasm2.h(q[0])
        qasm2.cx(q[0], q[1])
        qasm2.cx(q[1], q[2])

        return q

    target = PyQrack(3)

    q = target.run(ghz)

    assert isinstance(q, reg.PyQrackReg)

    out = q.sim_reg.out_ket()

    norm = math.sqrt(sum(abs(ele) ** 2 for ele in out))
    phase = out[0] / abs(out[0])

    out = [ele / (phase * norm) for ele in out]

    abs_tol = 2.2e-15

    assert all(math.isclose(ele.imag, 0.0, abs_tol=abs_tol) for ele in out)

    val = 1.0 / math.sqrt(2.0)

    assert math.isclose(out[0].real, val, abs_tol=abs_tol)
    assert math.isclose(out[-1].real, val, abs_tol=abs_tol)
    assert all(math.isclose(ele.real, 0.0, abs_tol=abs_tol) for ele in out[1:-1])


def test_target_glob():
    @qasm2.extended
    def global_h():
        q = qasm2.qreg(3)

        # rotate around Y by pi/2, i.e. perform a hadamard
        qasm2.glob.u([q], math.pi / 2.0, 0, 0)

        return q

    target = PyQrack(3)
    q = target.run(global_h)

    assert isinstance(q, reg.PyQrackReg)

    out = q.sim_reg.out_ket()

    # remove global phase introduced by pyqrack
    phase = out[0] / abs(out[0])
    out = [ele / phase for ele in out]

    for element in out:
        assert math.isclose(element.real, 1 / math.sqrt(8), abs_tol=2.2e-7)
        assert math.isclose(element.imag, 0, abs_tol=2.2e-7)

    @qasm2.extended
    def multiple_registers():
        q1 = qasm2.qreg(2)
        q2 = qasm2.qreg(2)
        q3 = qasm2.qreg(2)

        # hadamard on first register
        qasm2.glob.u(
            [q1],
            math.pi / 2.0,
            0,
            0,
        )

        # apply hadamard to the other two
        qasm2.glob.u(
            [q2, q3],
            math.pi / 2.0,
            0,
            0,
        )

        # rotate all of them back down
        qasm2.glob.u(
            [q1, q2, q3],
            -math.pi / 2.0,
            0,
            0,
        )

        return q1

    target = PyQrack(6)
    q1 = target.run(multiple_registers)

    assert isinstance(q1, reg.PyQrackReg)

    out = q1.sim_reg.out_ket()

    assert out[0] == 1
    for i in range(1, len(out)):
        assert out[i] == 0

    assert True


def test_measurement():

    @qasm2.main
    def measure_register():
        q = qasm2.qreg(2)
        c = qasm2.creg(2)
        qasm2.x(q[0])
        qasm2.cx(q[0], q[1])
        qasm2.measure(q, c)
        return c

    @qasm2.main
    def measure_single_qubits():
        q = qasm2.qreg(2)
        c = qasm2.creg(2)
        qasm2.x(q[0])
        qasm2.cx(q[0], q[1])
        qasm2.measure(q[0], c[0])
        qasm2.measure(q[1], c[1])
        return c

    target = PyQrack(2)
    result_single = target.run(measure_single_qubits)
    result_reg = target.run(measure_register)

    assert result_single == result_reg == [reg.Measurement.One, reg.Measurement.One]

    with pytest.raises(ir.TypeCheckError):

        @qasm2.main
        def measurement_that_errors():
            q = qasm2.qreg(1)
            c = qasm2.creg(1)
            qasm2.measure(q[0], c)
