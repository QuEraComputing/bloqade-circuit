from collections import Counter

from bloqade import qasm2
from bloqade.pyqrack import PyQrack


def test():

    @qasm2.extended
    def ghz(n: int):
        q = qasm2.qreg(n)
        c = qasm2.creg(n)

        qasm2.h(q[0])
        for i in range(1, n):
            qasm2.cx(q[0], q[i])

        for i in range(n):
            qasm2.measure(q[i], c[i])

        return c

    target = PyQrack(
        pyqrack_options={"isTensorNetwork": False, "isStabilizerHybrid": True},
        dynamic_qubits=True,
    )

    N = 50

    result = target.multi_run(ghz, 100, N)
    result = Counter("".join(str(int(bit)) for bit in bits) for bits in result)
    assert result.keys() == {"0" * N, "1" * N}
