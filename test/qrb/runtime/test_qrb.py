"""
Tests for the qrb (qrackbind) runtime, mirroring test/pyqrack/runtime/test_qrack.py.

Key qrackbind API differences reflected in mock assertions:
  - sim.measure(q)      instead of  sim.m(q)
  - sim.sdg(q)          instead of  sim.adjs(q)
  - sim.tdg(q)          instead of  sim.adjt(q)
  - sim.u(theta,phi,lam,q)  instead of  sim.u(q,theta,phi,lam)
  - sim.rx/ry/rz(angle,q)  instead of  sim.r(axis,angle,q)
  - sim.num_qubits      instead of  sim.num_qubits()   (property)
  - sim.state_vector    instead of  sim.out_ket()       (property)
"""

import math
from unittest.mock import Mock, call

import numpy as np
from kirin import ir

from bloqade import qasm2, squin
from bloqade.qrb import StackMemorySimulator
from bloqade.qrb.base import MockMemory, QRBInterpreter


def run_mock(program: ir.Method, rng_state: Mock | None = None):
    QRBInterpreter(
        program.dialects, memory=(memory := MockMemory()), rng_state=rng_state
    ).run(program)
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
            # qrackbind: sdg/tdg instead of pyqrack's adjs/adjt
            call.sdg(2),
            call.t(0),
            call.tdg(1),
            # qrackbind: u(theta, phi, lam, qubit)
            call.u(math.pi / 2, math.pi / 2, -math.pi / 2, 2),
            call.u(math.pi * 1.5, math.pi / 2, math.pi / 2, 0),
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

    # qrackbind: rx/ry/rz(angle, qubit) instead of pyqrack's r(Pauli, angle, qubit)
    sim_reg.assert_has_calls(
        [
            call.rx(0.5, 0),
            call.ry(0.5, 1),
            call.rz(0.5, 2),
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
    # qrackbind: u(theta, phi, lam, qubit)
    sim_reg.assert_has_calls(
        [
            call.u(0.5, 0.2, 0.1, 0),
            call.u(math.pi / 2, 0.2, 0.1, 1),
            call.u(0, 0, 0.2, 2),
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
        qasm2.swap(q[0], q[2])

    sim_reg = run_mock(program)
    sim_reg.assert_has_calls(
        [
            call.mcx([0], 1),
            call.mcy([1], 2),
            call.mcz([2], 0),
            # CH decomposed as mcu([ctrl], target, pi/2, 0, pi) until qrackbind>=0.3.0
            call.mcu([0], 1, math.pi / 2, 0, math.pi),
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
            # CRX decomposed as mcu(controls, target, lam, -pi/2, pi/2)
            call.mcu([0], 1, 0.5, -math.pi / 2, math.pi / 2),
            call.mcu([1], 2, 0, 0, 0.5),
            call.mcu([2], 0, 0.5, 0.2, 0.1),
            call.mcx([0, 1], 2),
            call.u(0, 0, 0.8, 0),
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
            # qrackbind: u(theta, phi, lam, qubit)
            call.u(0.5, 0.2, 0.1, 0),
            call.u(0.5, 0.2, 0.1, 1),
            # qrackbind: rz(angle, qubit) instead of r(3, phi, addr)
            call.rz(0.5, 0),
            call.rz(0.5, 1),
        ]
    )
