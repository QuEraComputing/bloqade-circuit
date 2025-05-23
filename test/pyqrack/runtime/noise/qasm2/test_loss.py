from typing import Literal
from unittest.mock import Mock

from kirin import ir
from kirin.dialects import ilist

from bloqade import qasm2
from bloqade.qasm2 import noise
from bloqade.pyqrack import PyQrackQubit, PyQrackInterpreter, reg
from bloqade.pyqrack.base import MockMemory


def run_mock(program: ir.Method, rng_state: Mock | None = None):
    PyQrackInterpreter(
        program.dialects, memory=(memory := MockMemory()), rng_state=rng_state
    ).run(program, ())
    assert isinstance(mock := memory.sim_reg, Mock)
    return mock


def test_atom_loss():

    @qasm2.extended
    def test_atom_loss(c: qasm2.CReg):
        q = qasm2.qreg(2)
        noise.atom_loss_channel([q[0]], prob=0.1)
        noise.atom_loss_channel([q[1]], prob=0.05)
        qasm2.measure(q[0], c[0])

        return q

    rng_state = Mock()
    rng_state.uniform.return_value = 0.1
    input = reg.CRegister(1)
    memory = MockMemory()

    result: ilist.IList[PyQrackQubit, Literal[2]] = PyQrackInterpreter(
        qasm2.extended, memory=memory, rng_state=rng_state
    ).run(test_atom_loss, (input,))

    assert result[0].state is reg.QubitState.Lost
    assert result[1].state is reg.QubitState.Active
    assert input[0] is reg.Measurement.One
