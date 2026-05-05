import math
from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.squin import gate
from bloqade.qrb.reg import QRBQubit
from bloqade.qrb.base import QRBInterpreter
from bloqade.squin.gate.stmts import (
    CX, CY, CZ, U3, H, S, T, X, Y, Z,
    Rx, Ry, Rz, SqrtX, SqrtY, PhasedXZ,
)


@gate.dialect.register(key="qrb")
class QRBMethods(interp.MethodTable):

    @interp.impl(X)
    @interp.impl(Y)
    @interp.impl(Z)
    @interp.impl(H)
    def single_qubit_gate(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: X | Y | Z | H
    ):
        qubits: ilist.IList[QRBQubit, Any] = frame.get(stmt.qubits)
        method_name = stmt.name.lower()
        for qbit in qubits:
            if qbit.is_active():
                getattr(qbit.sim_reg, method_name)(qbit.addr)

    @interp.impl(T)
    @interp.impl(S)
    def single_qubit_nh_gate(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: S | T
    ):
        qubits: ilist.IList[QRBQubit, Any] = frame.get(stmt.qubits)
        method_name = stmt.name.lower()
        if stmt.adjoint:
            # qrackbind: sdg/tdg instead of pyqrack's adjs/adjt
            method_name = method_name + "dg"
        for qbit in qubits:
            if qbit.is_active():
                getattr(qbit.sim_reg, method_name)(qbit.addr)

    @interp.impl(SqrtX)
    @interp.impl(SqrtY)
    def sqrt_xy(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: SqrtX | SqrtY
    ):
        angle = math.pi / 2
        if stmt.adjoint:
            angle *= -1

        qubits: ilist.IList[QRBQubit, Any] = frame.get(stmt.qubits)
        for qbit in qubits:
            if qbit.is_active():
                if isinstance(stmt, SqrtX):
                    # qrackbind: rx(angle, qubit)
                    qbit.sim_reg.rx(angle, qbit.addr)
                else:
                    qbit.sim_reg.ry(angle, qbit.addr)

    @interp.impl(Rx)
    @interp.impl(Ry)
    @interp.impl(Rz)
    def rot(self, interp: QRBInterpreter, frame: interp.Frame, stmt: Rx | Ry | Rz):
        qubits: ilist.IList[QRBQubit, Any] = frame.get(stmt.qubits)
        # NOTE: convert turns to radians
        angle = frame.get(stmt.angle) * 2 * math.pi

        for qbit in qubits:
            if qbit.is_active():
                match stmt:
                    case Rx():
                        # qrackbind: rx(angle, qubit) — note arg order vs pyqrack's r(axis, angle, qubit)
                        qbit.sim_reg.rx(angle, qbit.addr)
                    case Ry():
                        qbit.sim_reg.ry(angle, qbit.addr)
                    case Rz():
                        qbit.sim_reg.rz(angle, qbit.addr)

    @interp.impl(CX)
    @interp.impl(CY)
    @interp.impl(CZ)
    def control(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: CX | CY | CZ
    ):
        controls: ilist.IList[QRBQubit, Any] = frame.get(stmt.controls)
        targets: ilist.IList[QRBQubit, Any] = frame.get(stmt.targets)

        if len(controls) != len(targets):
            raise RuntimeError(
                f"Found {len(controls)} controls but {len(targets)} targets "
                f"when trying to evaluate {stmt}."
            )

        # qrackbind convention: mcx, mcy, mcz
        method_name = "m" + stmt.name.lower()

        for control, target in zip(controls, targets):
            if control.is_active() and target.is_active():
                getattr(control.sim_reg, method_name)([control.addr], target.addr)

    @interp.impl(U3)
    def u3(self, interp: QRBInterpreter, frame: interp.Frame, stmt: U3):
        theta = frame.get(stmt.theta) * 2 * math.pi
        phi = frame.get(stmt.phi) * 2 * math.pi
        lam = frame.get(stmt.lam) * 2 * math.pi
        qubits: ilist.IList[QRBQubit, Any] = frame.get(stmt.qubits)

        for qbit in qubits:
            if not qbit.is_active():
                continue
            # qrackbind: u(theta, phi, lam, qubit) — qubit is last arg
            qbit.sim_reg.u(theta, phi, lam, qbit.addr)

    @interp.impl(PhasedXZ)
    def phased_xz(
        self, interp: QRBInterpreter, frame: interp.Frame, stmt: PhasedXZ
    ):
        x_exponent = frame.get(stmt.x_exponent)
        z_exponent = frame.get(stmt.z_exponent)
        axis_phase_exponent = frame.get(stmt.axis_phase_exponent)
        qubits: ilist.IList[QRBQubit, Any] = frame.get(stmt.qubits)

        angle_rz_pre = -axis_phase_exponent * math.pi * 2
        angle_rx = x_exponent * math.pi * 2
        angle_rz_post = (axis_phase_exponent + z_exponent) * math.pi * 2

        for qbit in qubits:
            if not qbit.is_active():
                continue
            # qrackbind: rz(angle, qubit), rx(angle, qubit)
            qbit.sim_reg.rz(angle_rz_pre, qbit.addr)
            qbit.sim_reg.rx(angle_rx, qbit.addr)
            qbit.sim_reg.rz(angle_rz_post, qbit.addr)
