import math

from bloqade import qasm2
from pyqrack import QrackSimulator
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
    assert isinstance(q.sim_reg, QrackSimulator)

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


if __name__ == "__main__":
    test_target()
