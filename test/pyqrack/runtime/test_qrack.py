import math
from unittest.mock import Mock, call

from kirin import ir

from bloqade import qasm2
from pyqrack.pauli import Pauli
from bloqade.pyqrack.base import MockMemory, PyQrackInterpreter


def run_mock(program: ir.Method, rng_state: Mock | None = None):
    PyQrackInterpreter(
        program.dialects, memory=(memory := MockMemory()), rng_state=rng_state
    ).run(program, ())
    assert isinstance(mock := memory.sim_reg, Mock)
    return mock


def test_basic_gates():
    @qasm2.main
    def program():
        q = qasm2.qreg(3)

        qasm2.h(q[0])
        qasm2.x(q[1])
        qasm2.y(q[2])
        qasm2.z(q[0])
        qasm2.barrier((q[0], q[1]))
        qasm2.id(q[1])
        qasm2.s(q[1])
        qasm2.sdg(q[2])
        qasm2.t(q[0])
        qasm2.tdg(q[1])
        qasm2.sx(q[2])
        qasm2.sxdg(q[0])

    sim_reg = run_mock(program)
    sim_reg.assert_has_calls(
        [
            call.h(0),
            call.x(1),
            call.y(2),
            call.z(0),
            call.s(1),
            call.adjs(2),
            call.t(0),
            call.adjt(1),
            call.u(2, math.pi / 2, math.pi / 2, -math.pi / 2),
            call.u(0, math.pi * (1.5), math.pi / 2, math.pi / 2),
        ]
    )


def test_rotation_gates():
    @qasm2.main
    def program():
        q = qasm2.qreg(3)

        qasm2.rx(q[0], 0.5)
        qasm2.ry(q[1], 0.5)
        qasm2.rz(q[2], 0.5)

    sim_reg = run_mock(program)

    sim_reg.assert_has_calls(
        [
            call.r(Pauli.PauliX, 0.5, 0),
            call.r(Pauli.PauliY, 0.5, 1),
            call.r(Pauli.PauliZ, 0.5, 2),
        ]
    )


def test_u_gates():
    @qasm2.main
    def program():
        q = qasm2.qreg(3)

        qasm2.u(q[0], 0.5, 0.2, 0.1)
        qasm2.u2(q[1], 0.2, 0.1)
        qasm2.u1(q[2], 0.2)

    sim_reg = run_mock(program)
    sim_reg.assert_has_calls(
        [
            call.u(0, 0.5, 0.2, 0.1),
            call.u(1, math.pi / 2, 0.2, 0.1),
            call.u(2, 0, 0, 0.2),
        ]
    )


def test_basic_control_gates():

    @qasm2.main
    def program():
        q = qasm2.qreg(3)

        qasm2.cx(q[0], q[1])
        qasm2.cy(q[1], q[2])
        qasm2.cz(q[2], q[0])
        qasm2.ch(q[0], q[1])
        qasm2.csx(q[1], q[2])
        qasm2.swap(q[0], q[2])  # requires new bloqade version

    sim_reg = run_mock(program)
    sim_reg.assert_has_calls(
        [
            call.mcx([0], 1),
            call.mcy([1], 2),
            call.mcz([2], 0),
            call.mch([0], 1),
            call.mcu([1], 2, math.pi / 2, math.pi / 2, -math.pi / 2),
            call.swap(0, 2),
        ]
    )


def test_special_control():
    @qasm2.main
    def program():
        q = qasm2.qreg(3)

        qasm2.crx(q[0], q[1], 0.5)
        qasm2.cu1(q[1], q[2], 0.5)
        qasm2.cu3(q[2], q[0], 0.5, 0.2, 0.1)
        qasm2.ccx(q[0], q[1], q[2])
        qasm2.cu(q[0], q[1], 0.5, 0.2, 0.1, 0.8)
        qasm2.cswap(q[0], q[1], q[2])

    sim_reg = run_mock(program)
    sim_reg.assert_has_calls(
        [
            call.mcr(Pauli.PauliX, 0.5, [0], 1),
            call.mcu([1], 2, 0, 0, 0.5),
            call.mcu([2], 0, 0.5, 0.2, 0.1),
            call.mcx([0, 1], 2),
            call.u(0, 0.0, 0.0, 0.8),
            call.mcu([0], 1, 0.5, 0.2, 0.1),
            call.cswap([0], 1, 2),
        ]
    )


def test_extended():
    @qasm2.extended
    def program():
        q = qasm2.qreg(4)

        qasm2.parallel.cz(ctrls=[q[0], q[2]], qargs=[q[1], q[3]])
        qasm2.parallel.u([q[0], q[1]], theta=0.5, phi=0.2, lam=0.1)
        qasm2.parallel.rz([q[0], q[1]], 0.5)

    sim_reg = run_mock(program)
    sim_reg.assert_has_calls(
        [
            call.mcz([0], 1),
            call.mcz([2], 3),
            call.u(0, 0.5, 0.2, 0.1),
            call.u(1, 0.5, 0.2, 0.1),
            call.r(3, 0.5, 0),
            call.r(3, 0.5, 1),
        ]
    )
