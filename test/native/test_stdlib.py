import numpy as np

from bloqade.squin import qubit
from bloqade.native import kernel, stdlib
from bloqade.pyqrack import DynamicMemorySimulator


def test_ghz():

    @kernel
    def main():
        qreg = qubit.new(8)

        stdlib.h(qreg[0])
        for i in range(1, len(qreg)):
            stdlib.cx(qreg[i - 1], qreg[i])

    sv = DynamicMemorySimulator().state_vector(main)
    expected = np.zeros_like(sv)
    expected[0] = 1.0 / np.sqrt(2.0)
    expected[-1] = 1.0 / np.sqrt(2.0)

    assert np.abs(np.vdot(sv, expected)) - 1 < 1e-6
