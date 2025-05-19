from unittest.mock import Mock, call

import pytest
from kirin import ir

from bloqade import qasm2
from bloqade.qasm2 import noise
from bloqade.pyqrack.base import MockMemory, PyQrackInterpreter


def run_mock(program: ir.Method, rng_state: Mock | None = None):
    PyQrackInterpreter(
        program.dialects, memory=(memory := MockMemory()), rng_state=rng_state
    ).run(program, ())
    assert isinstance(mock := memory.sim_reg, Mock)
    return mock


def test_pauli_channel():
    @qasm2.extended
    def test_atom_loss():
        q = qasm2.qreg(2)
        noise.pauli_channel(
            [q[0]],
            px=0.1,
            py=0.4,
            pz=0.3,
        )
        noise.pauli_channel(
            [q[1]],
            px=0.1,
            py=0.4,
            pz=0.3,
        )
        return q

    rng_state = Mock()
    rng_state.choice.side_effect = ["y", "i"]
    sim_reg = run_mock(test_atom_loss, rng_state)
    sim_reg.assert_has_calls([call.y(0)])


@pytest.mark.xfail
def test_pauli_probs_check():
    @qasm2.extended
    def test_atom_loss():
        q = qasm2.qreg(2)
        noise.pauli_channel(
            [q[0]],
            px=0.1,
            py=0.4,
            pz=1.3,
        )
        return q

    with pytest.raises(ir.ValidationError):
        test_atom_loss.verify()


def test_cz_pauli_channel_false():
    @qasm2.extended
    def test_atom_loss():
        q = qasm2.qreg(2)
        noise.atom_loss_channel([q[0]], prob=0.4)
        noise.atom_loss_channel([q[1]], prob=0.4)
        noise.cz_pauli_channel(
            [q[0]],
            [q[1]],
            px_ctrl=0.1,
            py_ctrl=0.4,
            pz_ctrl=0.3,
            px_qarg=0.2,
            py_qarg=0.2,
            pz_qarg=0.2,
            paired=False,
        )  # no noise here
        qasm2.cz(q[0], q[1])
        noise.atom_loss_channel([q[0]], prob=0.7)
        noise.atom_loss_channel([q[1]], prob=0.4)
        noise.cz_pauli_channel(
            [q[0]],
            [q[1]],
            px_ctrl=0.1,
            py_ctrl=0.4,
            pz_ctrl=0.3,
            px_qarg=0.2,
            py_qarg=0.2,
            pz_qarg=0.2,
            paired=False,
        )
        qasm2.cz(q[0], q[1])
        return q

    rng_state = Mock()
    rng_state.choice.side_effect = ["y"]
    rng_state.uniform.return_value = 0.5
    sim_reg = run_mock(test_atom_loss, rng_state)
    sim_reg.assert_has_calls([call.mcz([0], 1), call.m(0), call.y(1)])


def test_cz_pauli_channel_true():
    @qasm2.extended
    def test_atom_loss():
        q = qasm2.qreg(2)
        noise.atom_loss_channel([q[0]], prob=0.4)
        noise.atom_loss_channel([q[1]], prob=0.4)
        noise.cz_pauli_channel(
            [q[0]],
            [q[1]],
            px_ctrl=0.1,
            py_ctrl=0.4,
            pz_ctrl=0.3,
            px_qarg=0.2,
            py_qarg=0.2,
            pz_qarg=0.2,
            paired=True,
        )  # no noise here
        qasm2.cz(q[0], q[1])
        noise.atom_loss_channel([q[0]], prob=0.7)
        noise.atom_loss_channel([q[1]], prob=0.4)
        noise.cz_pauli_channel(
            [q[0]],
            [q[1]],
            px_ctrl=0.1,
            py_ctrl=0.4,
            pz_ctrl=0.3,
            px_qarg=0.2,
            py_qarg=0.2,
            pz_qarg=0.2,
            paired=True,
        )
        qasm2.cz(q[0], q[1])
        return q

    rng_state = Mock()
    rng_state.choice.side_effect = ["y", "x"]
    rng_state.uniform.return_value = 0.5
    sim_reg = run_mock(test_atom_loss, rng_state)

    sim_reg.assert_has_calls([call.y(0), call.x(1), call.mcz([0], 1)])
