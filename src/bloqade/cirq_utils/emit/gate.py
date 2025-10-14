import math

import cirq
from kirin.interp import MethodTable, impl

from bloqade.squin import gate

from .base import EmitCirq, EmitCirqFrame


@gate.dialect.register(key="emit.cirq")
class __EmitCirqGateMethods(MethodTable):

    @impl(gate.stmts.X)
    @impl(gate.stmts.Y)
    @impl(gate.stmts.Z)
    @impl(gate.stmts.H)
    def hermitian(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: gate.stmts.SingleQubitGate
    ):
        qubits = frame.get(stmt.qubits)
        cirq_op = getattr(cirq, stmt.name.upper())
        frame.circuit.append(cirq_op.on_each(qubits))
        return ()

    @impl(gate.stmts.S)
    @impl(gate.stmts.T)
    def unitary(
        self,
        emit: EmitCirq,
        frame: EmitCirqFrame,
        stmt: gate.stmts.SingleQubitNonHermitianGate,
    ):
        qubits = frame.get(stmt.qubits)
        cirq_op = getattr(cirq, stmt.name.upper())
        if stmt.adjoint:
            cirq_op = cirq_op ** (-1)

        frame.circuit.append(cirq_op.on_each(qubits))
        return ()

    @impl(gate.stmts.SqrtX)
    @impl(gate.stmts.SqrtY)
    def sqrt(
        self,
        emit: EmitCirq,
        frame: EmitCirqFrame,
        stmt: gate.stmts.SqrtX | gate.stmts.SqrtY,
    ):
        qubits = frame.get(stmt.qubits)

        exponent = 0.5
        if stmt.adjoint:
            exponent *= -1

        if isinstance(stmt, gate.stmts.SqrtX):
            cirq_op = cirq.XPowGate(exponent=exponent)
        else:
            cirq_op = cirq.YPowGate(exponent=exponent)

        frame.circuit.append(cirq_op.on_each(qubits))
        return ()

    @impl(gate.stmts.CX)
    @impl(gate.stmts.CY)
    @impl(gate.stmts.CZ)
    def control(
        self, emit: EmitCirq, frame: EmitCirqFrame, stmt: gate.stmts.ControlledGate
    ):
        controls = frame.get(stmt.controls)
        targets = frame.get(stmt.targets)
        cirq_op = getattr(cirq, stmt.name.upper())
        cirq_qubits = [(ctrl, target) for ctrl, target in zip(controls, targets)]
        frame.circuit.append(cirq_op.on_each(cirq_qubits))
        return ()

    @impl(gate.stmts.Rx)
    @impl(gate.stmts.Ry)
    @impl(gate.stmts.Rz)
    def rot(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: gate.stmts.RotationGate):
        qubits = frame.get(stmt.qubits)

        turns = frame.get(stmt.angle)
        angle = turns * 2 * math.pi
        cirq_op = getattr(cirq, stmt.name.title())(rads=angle)

        frame.circuit.append(cirq_op.on_each(qubits))
        return ()

    @impl(gate.stmts.U3)
    def u3(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: gate.stmts.U3):
        qubits = frame.get(stmt.qubits)

        theta = frame.get(stmt.theta) * 2 * math.pi
        phi = frame.get(stmt.phi) * 2 * math.pi
        lam = frame.get(stmt.lam) * 2 * math.pi

        frame.circuit.append(cirq.Rz(rads=lam).on_each(*qubits))

        frame.circuit.append(cirq.Ry(rads=theta).on_each(*qubits))

        frame.circuit.append(cirq.Rz(rads=phi).on_each(*qubits))

        return ()
