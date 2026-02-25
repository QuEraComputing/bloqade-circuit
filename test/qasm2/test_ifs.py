import textwrap

import pytest
from kirin.ir.exception import ValidationErrorGroup

from bloqade import qasm2
from bloqade.pyqrack import StackMemorySimulator
from bloqade.qasm2.emit import QASM2


def test_simulator():

    @qasm2.main
    def main():
        qreg = qasm2.qreg(2)
        creg = qasm2.creg(2)
        qasm2.x(qreg[0])

        # NOTE: all these should evaluate to True
        if creg[0] == 1:
            qasm2.x(qreg[1])

        qasm2.measure(qreg, creg)
        if creg == 3:
            qasm2.x(qreg[1])

        qasm2.measure(qreg, creg)
        if 1 == creg:
            qasm2.x(qreg[1])

        qasm2.measure(qreg, creg)
        if creg == creg:
            qasm2.x(qreg[1])

        # NOTE: we skipped a measurement so we should be in 11 still
        if creg[0] == creg[1]:
            qasm2.x(qreg[1])

        qasm2.measure(qreg, creg)
        return creg

    sim = StackMemorySimulator(min_qubits=2)
    task = sim.task(main)
    result = task.run()
    assert result == [1, 1]


def test_emit():
    @qasm2.main
    def main():
        qreg = qasm2.qreg(2)
        creg = qasm2.creg(2)
        qasm2.x(qreg[0])
        qasm2.x(qreg[1])

        qasm2.measure(qreg, creg)
        if creg == 3:
            qasm2.x(qreg[1])

        qasm2.measure(qreg, creg)
        return creg

    target = QASM2()
    qasm2_str = target.emit_str(main)

    expected_str = textwrap.dedent("""        OPENQASM 2.0;
        include "qelib1.inc";
        qreg qreg[2];
        creg creg[2];
        x qreg[0];
        x qreg[1];
        measure qreg -> creg;
        if (creg == 3) x qreg[1];
        measure qreg -> creg;
        """)
    assert qasm2_str == expected_str

    @qasm2.main
    def main_reversed_order():
        qreg = qasm2.qreg(2)
        creg = qasm2.creg(2)
        qasm2.x(qreg[0])
        qasm2.x(qreg[1])

        qasm2.measure(qreg, creg)
        if 3 == creg:
            qasm2.x(qreg[1])

        qasm2.measure(qreg, creg)
        return creg

    target = QASM2()
    qasm2_str = target.emit_str(main_reversed_order)
    assert qasm2_str == expected_str

    @qasm2.main
    def main_invalid():
        qreg = qasm2.qreg(2)
        creg = qasm2.creg(2)
        qasm2.x(qreg[0])
        qasm2.x(qreg[1])

        qasm2.measure(qreg, creg)
        if creg[0] == 1:
            qasm2.x(qreg[1])

        qasm2.measure(qreg, creg)
        return creg

    target = QASM2()

    with pytest.raises(ValidationErrorGroup):
        target.emit(main_invalid)
