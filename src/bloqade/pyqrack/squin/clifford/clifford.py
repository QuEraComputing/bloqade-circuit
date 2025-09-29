import math
from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.squin import clifford
from pyqrack.pauli import Pauli
from bloqade.pyqrack.reg import PyQrackQubit
from bloqade.pyqrack.target import PyQrackInterpreter
from bloqade.squin.clifford.stmts import (
    CX,
    CY,
    CZ,
    H,
    S,
    T,
    X,
    Y,
    Z,
    Rx,
    Ry,
    Rz,
    SqrtX,
    SqrtY,
)


@clifford.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):

    @interp.impl(X)
    @interp.impl(Y)
    @interp.impl(Z)
    @interp.impl(H)
    def single_qubit_gate(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: X | Y | Z | H
    ):
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        method_name = stmt.name.lower()
        for qbit in qubits:
            if qbit.is_active():
                getattr(qbit.sim_reg, method_name)(qbit.addr)

    @interp.impl(T)
    @interp.impl(S)
    def single_qubit_nh_gate(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: S | T
    ):
        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)

        method_name = stmt.name.lower()
        if stmt.adjoint:
            method_name = "adj" + method_name

        for qbit in qubits:
            if qbit.is_active():
                getattr(qbit.sim_reg, method_name)(qbit.addr)
                qbit.sim_reg.r

    @interp.impl(SqrtX)
    @interp.impl(SqrtY)
    def sqrt_x(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: SqrtX | SqrtY
    ):
        angle = math.pi / 2

        if isinstance(stmt, SqrtX):
            axis = Pauli.PauliX
        else:
            angle *= -1
            axis = Pauli.PauliY

        if stmt.adjoint:
            angle *= -1

        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)
        for qbit in qubits:
            if qbit.is_active():
                qbit.sim_reg.r(axis, angle, qbit.addr)

    @interp.impl(Rx)
    @interp.impl(Ry)
    @interp.impl(Rz)
    def rot(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: Rx | Ry | Rz):
        match stmt:
            case Rx():
                axis = Pauli.PauliX
            case Ry():
                axis = Pauli.PauliY
            case Rz():
                axis = Pauli.PauliZ

        qubits: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.qubits)

        # NOTE: convert turns to radians
        angle = frame.get(stmt.angle) * 2 * math.pi

        for qbit in qubits:
            if qbit.is_active():
                qbit.sim_reg.r(axis, angle, qbit.addr)

    @interp.impl(CX)
    @interp.impl(CY)
    @interp.impl(CZ)
    def control(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: CX | CY | CZ
    ):
        controls: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.controls)
        targets: ilist.IList[PyQrackQubit, Any] = frame.get(stmt.targets)

        if len(controls) != len(targets):
            raise RuntimeError(
                f"Found {len(controls)} controls but {len(targets)} targets when trying to evaluate {stmt}."
            )

        # NOTE: pyqrack convention "multi-control-x"
        method_name = "m" + stmt.name.lower()

        for control, target in zip(controls, targets):
            if control.is_active() and target.is_active():
                getattr(control.sim_reg, method_name)([control.addr], target.addr)
