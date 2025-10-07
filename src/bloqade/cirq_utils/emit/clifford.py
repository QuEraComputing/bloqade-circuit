import math

import cirq
from kirin.interp import MethodTable, impl

from bloqade.squin import clifford

from .base import EmitCirq, EmitCirqFrame


@clifford.dialect.register(key="emit.cirq")
class __EmitCirqCliffordMethods(MethodTable):

    @impl(clifford.stmts.X)
    @impl(clifford.stmts.Y)
    @impl(clifford.stmts.Z)
    @impl(clifford.stmts.H)
    def hermitian(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: clifford.stmts.SingleQubitGate
    ):
        qubits = frame.get(stmt.qubits)
        cirq_op = getattr(cirq, stmt.name.upper())
        frame.circuit.append(cirq_op.on_each(qubits))
        return ()

    @impl(clifford.stmts.S)
    @impl(clifford.stmts.T)
    def unitary(
        self,
        emit: EmitCirq,
        frame: EmitCirqFrame,
        stmt: clifford.stmts.SingleQubitNonHermitianGate,
    ):
        qubits = frame.get(stmt.qubits)
        cirq_op = getattr(cirq, stmt.name.upper())
        if stmt.adjoint:
            cirq_op = cirq_op ** (-1)

        frame.circuit.append(cirq_op.on_each(qubits))
        return ()

    @impl(clifford.stmts.SqrtX)
    @impl(clifford.stmts.SqrtY)
    def sqrt(
        self,
        emit: EmitCirq,
        frame: EmitCirqFrame,
        stmt: clifford.stmts.SqrtX | clifford.stmts.SqrtY,
    ):
        qubits = frame.get(stmt.qubits)

        exponent = 0.5
        if stmt.adjoint:
            exponent *= -1

        if isinstance(stmt, clifford.stmts.SqrtX):
            cirq_op = cirq.XPowGate(exponent=exponent)
        else:
            cirq_op = cirq.YPowGate(exponent=exponent)

        frame.circuit.append(cirq_op.on_each(qubits))
        return ()

    @impl(clifford.stmts.CX)
    @impl(clifford.stmts.CY)
    @impl(clifford.stmts.CZ)
    def control(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: clifford.stmts.ControlledGate
    ):
        controls = frame.get(stmt.controls)
        targets = frame.get(stmt.targets)
        cirq_op = getattr(cirq, stmt.name.upper())
        cirq_qubits = [(ctrl, target) for ctrl, target in zip(controls, targets)]
        frame.circuit.append(cirq_op.on_each(cirq_qubits))
        return ()

    @impl(clifford.stmts.Rx)
    @impl(clifford.stmts.Ry)
    @impl(clifford.stmts.Rz)
    def rot(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: clifford.stmts.RotationGate
    ):
        qubits = frame.get(stmt.qubits)

        turns = frame.get(stmt.angle)
        angle = turns * 2 * math.pi
        cirq_op = getattr(cirq, stmt.name.title())(rads=angle)

        frame.circuit.append(cirq_op.on_each(qubits))
        return ()
