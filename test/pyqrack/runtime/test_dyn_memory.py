from typing import cast
from collections import Counter

from bloqade import qasm2
from bloqade.pyqrack import CRegister, DynamicMemorySimulator


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

    target = DynamicMemorySimulator(
        options={"isTensorNetwork": False, "isStabilizerHybrid": True},
    )

    N = 20

    shots = Counter()
    task = target.task(ghz, (N,))
    for _ in range(100):
        result = cast(CRegister, task.run())
        shots[("".join(map(str, map(int, result))))] += 1

    assert shots.keys() == {"0" * N, "1" * N}
