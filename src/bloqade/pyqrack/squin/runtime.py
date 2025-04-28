from dataclasses import dataclass

import numpy as np

from bloqade.pyqrack import PyQrackQubit


@dataclass(frozen=True)
class OperatorRuntimeABC:
    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        raise NotImplementedError(
            "Operator runtime base class should not be called directly, override the method"
        )

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        raise NotImplementedError(f"Can't apply controlled version of {self}")


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

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        method_name = self.get_method_name(adjoint=adjoint, control=False)
        getattr(qubits[0].sim_reg, method_name)(qubits[0].addr)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        ctrls = [qbit.addr for qbit in qubits[:-1]]
        target = qubits[-1]
        method_name = self.get_method_name(adjoint=adjoint, control=True)
        getattr(target.sim_reg, method_name)(target.addr, ctrls)


@dataclass(frozen=True)
class ControlRuntime(OperatorRuntimeABC):
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

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        qubits[0].sim_reg.force_m(qubits[0].addr, self.to_state)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        m = [not self.to_state, 0, 0, self.to_state]
        target = qubits[-1]
        ctrls = [qbit.addr for qbit in qubits[:-1]]
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
class KronRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        self.lhs.apply(qubits[0], adjoint=adjoint)
        self.rhs.apply(qubits[1], adjoint=adjoint)


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
        self.op.apply(*qubits, adjoint=adjoint)

        target = qubits[-1]

        # NOTE: just factor * eye(2)
        m = self.mat(adjoint)

        # TODO: output seems to always be normalized -- no-op?
        target.sim_reg.mtrx(m, target.addr)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        self.op.control_apply(*qubits, adjoint=adjoint)

        target = qubits[-1]
        ctrls = [qbit.addr for qbit in qubits[:-1]]

        m = self.mat(adjoint=adjoint)

        target.sim_reg.mcmtrx(ctrls, m, target.addr)


@dataclass(frozen=True)
class MtrxOpRuntime(OperatorRuntimeABC):
    def mat(self, adjoint: bool) -> list[complex]:
        raise NotImplementedError("Override this method in the subclass!")

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        m = self.mat(adjoint=adjoint)
        target.sim_reg.mtrx(m, target.addr)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        target = qubits[-1]
        ctrls = [qbit.addr for qbit in qubits[:-1]]

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
        phase = np.exp(sign * 1j * self.theta)
        return [self.global_ * phase, 0, 0, phase]


@dataclass(frozen=True)
class RotRuntime(OperatorRuntimeABC):
    axis: OperatorRuntimeABC
    angle: float
    # TODO: how does this work?


@dataclass(frozen=True)
class AdjointRuntime(OperatorRuntimeABC):
    op: OperatorRuntimeABC

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = True) -> None:
        self.op.apply(*qubits, adjoint=adjoint)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = True) -> None:
        self.op.control_apply(*qubits, adjoint=adjoint)
