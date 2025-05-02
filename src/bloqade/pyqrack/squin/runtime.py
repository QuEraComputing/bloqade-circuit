from typing import Any
from dataclasses import field, dataclass

import numpy as np
from kirin.dialects import ilist

from pyqrack.pauli import Pauli
from bloqade.pyqrack import PyQrackQubit


@dataclass(frozen=True)
class OperatorRuntimeABC:
    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        raise NotImplementedError(
            "Operator runtime base class should not be called directly, override the method"
        )

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        raise RuntimeError(f"Can't apply controlled version of {self}")

    def broadcast_apply(self, qubits: ilist.IList[PyQrackQubit, Any], **kwargs) -> None:
        for qbit in qubits:
            if not qbit.is_active():
                continue

            self.apply(qbit, **kwargs)


@dataclass(frozen=True)
class NonBroadcastableOperatorRuntimeABC(OperatorRuntimeABC):
    def broadcast_apply(self, qubits: ilist.IList[PyQrackQubit, Any], **kwargs) -> None:
        raise RuntimeError(
            f"Operator of type {type(self).__name__} is not broadcastable!"
        )


@dataclass(frozen=True)
class OperatorRuntime(OperatorRuntimeABC):
    method_name: str

    def get_method_name(self, adjoint: bool, control: bool) -> str:
        method_name = ""
        if control:
            method_name += "mc"

        if adjoint and self.method_name in ("s", "t"):
            method_name += "adj"

        return method_name + self.method_name

    def apply(self, qubit: PyQrackQubit, adjoint: bool = False) -> None:
        if not qubit.is_active():
            return
        method_name = self.get_method_name(adjoint=adjoint, control=False)
        getattr(qubit.sim_reg, method_name)(qubit.addr)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        if not target.is_active():
            return

        ctrls = [qbit.addr for qbit in qubits[:-1] if qbit.is_active()]
        if len(ctrls) == 0:
            return

        method_name = self.get_method_name(adjoint=adjoint, control=True)
        getattr(target.sim_reg, method_name)(ctrls, target.addr)


@dataclass(frozen=True)
class ControlRuntime(NonBroadcastableOperatorRuntimeABC):
    op: OperatorRuntimeABC
    n_controls: int

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        # NOTE: this is a bit odd, since you can "skip" qubits by making n_controls < len(qubits)
        ctrls = qubits[: self.n_controls]
        target = qubits[-1]
        self.op.control_apply(target, *ctrls, adjoint=adjoint)


@dataclass(frozen=True)
class ProjectorRuntime(OperatorRuntimeABC):
    to_state: bool

    def apply(self, qubit: PyQrackQubit, adjoint: bool = False) -> None:
        if not qubit.is_active():
            return
        qubit.sim_reg.force_m(qubit.addr, self.to_state)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        if not target.is_active():
            return

        ctrls = [qbit.addr for qbit in qubits[:-1]]

        m = [not self.to_state, 0, 0, self.to_state]
        target.sim_reg.mcmtrx(ctrls, m, target.addr)


@dataclass(frozen=True)
class IdentityRuntime(OperatorRuntimeABC):
    # TODO: do we even need sites? The apply never does anything
    sites: int

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        pass

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        pass


@dataclass(frozen=True)
class MultRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        if adjoint:
            # NOTE: inverted order
            self.lhs.apply(*qubits, adjoint=adjoint)
            self.rhs.apply(*qubits, adjoint=adjoint)
        else:
            self.rhs.apply(*qubits)
            self.lhs.apply(*qubits)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        if adjoint:
            self.lhs.control_apply(*qubits, adjoint=adjoint)
            self.rhs.control_apply(*qubits, adjoint=adjoint)
        else:
            self.rhs.control_apply(*qubits, adjoint=adjoint)
            self.lhs.control_apply(*qubits, adjoint=adjoint)


@dataclass(frozen=True)
class KronRuntime(NonBroadcastableOperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        self.lhs.apply(qubits[0], adjoint=adjoint)
        self.rhs.apply(qubits[1], adjoint=adjoint)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        # FIXME: this feels a bit weird and it's not very clear semantically
        # for now I'm settling for: apply to qubits if ctrls, using the same ctrls
        # for both targets
        assert len(qubits) > 2
        target1 = qubits[-2]
        target2 = qubits[-1]
        ctrls = qubits[:-2]
        self.lhs.control_apply(*ctrls, target1, adjoint=adjoint)
        self.rhs.control_apply(*ctrls, target2, adjoint=adjoint)


@dataclass(frozen=True)
class ScaleRuntime(OperatorRuntimeABC):
    op: OperatorRuntimeABC
    factor: complex

    def mat(self, adjoint: bool):
        if adjoint:
            return [np.conj(self.factor), 0, 0, self.factor]
        else:
            return [self.factor, 0, 0, self.factor]

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        if not target.is_active():
            return

        self.op.apply(*qubits, adjoint=adjoint)

        # NOTE: just factor * eye(2)
        m = self.mat(adjoint)

        # TODO: output seems to always be normalized -- no-op?
        target.sim_reg.mtrx(m, target.addr)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        if not target.is_active():
            return

        ctrls = [qbit.addr for qbit in qubits[:-1] if qbit.is_active()]
        if len(ctrls) == 0:
            return

        self.op.control_apply(*qubits, adjoint=adjoint)
        m = self.mat(adjoint=adjoint)
        target.sim_reg.mcmtrx(ctrls, m, target.addr)


@dataclass(frozen=True)
class MtrxOpRuntime(OperatorRuntimeABC):
    def mat(self, adjoint: bool) -> list[complex]:
        raise NotImplementedError("Override this method in the subclass!")

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        if not target.is_active():
            return

        m = self.mat(adjoint=adjoint)
        target.sim_reg.mtrx(m, target.addr)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        if not target.is_active():
            return

        ctrls = [qbit.addr for qbit in qubits[:-1] if qbit.is_active()]
        if len(ctrls) == 0:
            return

        m = self.mat(adjoint=adjoint)
        target.sim_reg.mcmtrx(ctrls, m, target.addr)


@dataclass(frozen=True)
class SpRuntime(MtrxOpRuntime):
    def mat(self, adjoint: bool) -> list[complex]:
        if adjoint:
            return [0, 0, 0.5, 0]
        else:
            return [0, 0.5, 0, 0]


@dataclass(frozen=True)
class SnRuntime(MtrxOpRuntime):
    def mat(self, adjoint: bool) -> list[complex]:
        if adjoint:
            return [0, 0.5, 0, 0]
        else:
            return [0, 0, 0.5, 0]


@dataclass(frozen=True)
class PhaseOpRuntime(MtrxOpRuntime):
    theta: float
    global_: bool

    def mat(self, adjoint: bool) -> list[complex]:
        sign = (-1) ** (not adjoint)
        local_phase = np.exp(sign * 1j * self.theta)

        # NOTE: this is just 1 if we want a local shift
        global_phase = np.exp(sign * 1j * self.theta * self.global_)

        return [global_phase, 0, 0, local_phase]


@dataclass(frozen=True)
class RotRuntime(OperatorRuntimeABC):
    axis: OperatorRuntimeABC
    angle: float
    pyqrack_axis: Pauli = field(init=False)

    def __post_init__(self):
        if not isinstance(self.axis, OperatorRuntime):
            raise RuntimeError(
                f"Rotation only supported for Pauli operators! Got {self.axis}"
            )

        try:
            axis = getattr(Pauli, "Pauli" + self.axis.method_name.upper())
        except KeyError:
            raise RuntimeError(
                f"Rotation only supported for Pauli operators! Got {self.axis}"
            )

        # NOTE: weird setattr for frozen dataclasses
        object.__setattr__(self, "pyqrack_axis", axis)

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        if not target.is_active():
            return

        sign = (-1) ** adjoint
        angle = sign * self.angle
        target.sim_reg.r(self.pyqrack_axis, angle, target.addr)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        if not target.is_active():
            return

        ctrls = [qbit.addr for qbit in qubits[:-1] if qbit.is_active()]
        if len(ctrls) == 0:
            return

        sign = (-1) ** (not adjoint)
        angle = sign * self.angle
        target.sim_reg.mcr(self.pyqrack_axis, angle, ctrls, target.addr)


@dataclass(frozen=True)
class AdjointRuntime(OperatorRuntimeABC):
    op: OperatorRuntimeABC

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = True) -> None:
        self.op.apply(*qubits, adjoint=adjoint)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = True) -> None:
        self.op.control_apply(*qubits, adjoint=adjoint)


@dataclass(frozen=True)
class U3Runtime(OperatorRuntimeABC):
    theta: float
    phi: float
    lam: float

    def angles(self, adjoint: bool) -> tuple[float, float, float]:
        if adjoint:
            # NOTE: adjoint(U(theta, phi, lam)) == U(-theta, -lam, -phi)
            return -self.theta, -self.lam, -self.phi
        else:
            return self.theta, self.phi, self.lam

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        if not target.is_active():
            return

        angles = self.angles(adjoint=adjoint)
        target.sim_reg.u(target.addr, *angles)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        if not target.is_active():
            return

        ctrls = [qbit.addr for qbit in qubits[:-1] if qbit.is_active()]
        if len(ctrls) == 0:
            return

        angles = self.angles(adjoint=adjoint)
        target.sim_reg.mcu(ctrls, target.addr, *angles)


@dataclass(frozen=True)
class PauliStringRuntime(NonBroadcastableOperatorRuntimeABC):
    string: str
    ops: list[OperatorRuntime]

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False):
        if len(self.ops) != len(qubits):
            raise RuntimeError(
                f"Cannot apply Pauli string {self.string} to {len(qubits)} qubits! Make sure the length matches."
            )

        for i, op in enumerate(self.ops):
            op.apply(qubits[i], adjoint=adjoint)
