from typing import Any
from dataclasses import field, dataclass

import numpy as np
from kirin.dialects import ilist

from pyqrack.pauli import Pauli
from bloqade.pyqrack import PyQrackQubit


@dataclass(frozen=True)
class OperatorRuntimeABC:
    """The number of sites the operator applies to (including controls)"""

    @property
    def n_sites(self) -> int: ...

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        raise NotImplementedError(
            "Operator runtime base class should not be called directly, override the method"
        )

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit, ...],
        adjoint: bool = False,
    ) -> None:
        raise RuntimeError(f"Can't apply controlled version of {self}")

    def broadcast_apply(self, qubits: ilist.IList[PyQrackQubit, Any], **kwargs) -> None:
        n = self.n_sites

        if len(qubits) % n != 0:
            raise RuntimeError(
                f"Cannot broadcast operator {self} that applies to {n} over {len(qubits)} qubits."
            )

        for qubit_index in range(0, len(qubits), n):
            targets = qubits[qubit_index : qubit_index + n]
            self.apply(*targets, **kwargs)


@dataclass(frozen=True)
class ResetRuntime(OperatorRuntimeABC):
    """Reset the qubit to the target state"""

    target_state: bool

    @property
    def n_sites(self) -> int:
        return 1

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        for qubit in qubits:
            if not qubit.is_active():
                continue

            res: bool = qubit.sim_reg.m(qubit.addr)
            if res != self.target_state:
                qubit.sim_reg.x(qubit.addr)


@dataclass(frozen=True)
class OperatorRuntime(OperatorRuntimeABC):
    method_name: str

    @property
    def n_sites(self) -> int:
        return 1

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

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit],
        adjoint: bool = False,
    ) -> None:
        target = targets[0]
        if not target.is_active():
            return

        ctrls: list[int] = []
        for qbit in controls:
            if not qbit.is_active():
                return

            ctrls.append(qbit.addr)

        method_name = self.get_method_name(adjoint=adjoint, control=True)
        getattr(target.sim_reg, method_name)(ctrls, target.addr)


@dataclass(frozen=True)
class ControlRuntime(OperatorRuntimeABC):
    op: OperatorRuntimeABC
    n_controls: int

    @property
    def n_sites(self) -> int:
        return self.op.n_sites + self.n_controls

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        ctrls = qubits[: self.n_controls]
        targets = qubits[self.n_controls :]

        if len(targets) != self.op.n_sites:
            raise RuntimeError(
                f"Cannot apply operator {self.op} to {len(targets)} qubits! It applies to {self.op.n_sites}, check your inputs!"
            )

        self.op.control_apply(controls=ctrls, targets=targets, adjoint=adjoint)


@dataclass(frozen=True)
class ProjectorRuntime(OperatorRuntimeABC):
    to_state: bool

    @property
    def n_sites(self) -> int:
        return 1

    def apply(self, qubit: PyQrackQubit, adjoint: bool = False) -> None:
        if not qubit.is_active():
            return
        qubit.sim_reg.force_m(qubit.addr, self.to_state)

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit],
        adjoint: bool = False,
    ) -> None:
        target = targets[0]
        if not target.is_active():
            return

        ctrls: list[int] = []
        for qbit in controls:
            if not qbit.is_active():
                return

        m = [not self.to_state, 0, 0, self.to_state]
        target.sim_reg.mcmtrx(ctrls, m, target.addr)


@dataclass(frozen=True)
class IdentityRuntime(OperatorRuntimeABC):
    # TODO: do we even need sites? The apply never does anything
    sites: int

    @property
    def n_sites(self) -> int:
        return self.sites

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        pass

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit, ...],
        adjoint: bool = False,
    ) -> None:
        pass


@dataclass(frozen=True)
class MultRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    @property
    def n_sites(self) -> int:
        if self.lhs.n_sites != self.rhs.n_sites:
            raise RuntimeError("Multiplication of operators with unequal size.")

        return self.lhs.n_sites

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        if adjoint:
            # NOTE: inverted order
            self.lhs.apply(*qubits, adjoint=adjoint)
            self.rhs.apply(*qubits, adjoint=adjoint)
        else:
            self.rhs.apply(*qubits)
            self.lhs.apply(*qubits)

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit, ...],
        adjoint: bool = False,
    ) -> None:
        if adjoint:
            self.lhs.control_apply(controls=controls, targets=targets, adjoint=adjoint)
            self.rhs.control_apply(controls=controls, targets=targets, adjoint=adjoint)
        else:
            self.rhs.control_apply(controls=controls, targets=targets, adjoint=adjoint)
            self.lhs.control_apply(controls=controls, targets=targets, adjoint=adjoint)


@dataclass(frozen=True)
class KronRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    @property
    def n_sites(self) -> int:
        return self.lhs.n_sites + self.rhs.n_sites

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        self.lhs.apply(*qubits[: self.lhs.n_sites], adjoint=adjoint)
        self.rhs.apply(*qubits[self.lhs.n_sites :], adjoint=adjoint)

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit, ...],
        adjoint: bool = False,
    ) -> None:
        self.lhs.control_apply(
            controls=controls,
            targets=tuple(targets[: self.lhs.n_sites]),
            adjoint=adjoint,
        )
        self.rhs.control_apply(
            controls=controls,
            targets=tuple(targets[self.lhs.n_sites :]),
            adjoint=adjoint,
        )


@dataclass(frozen=True)
class ScaleRuntime(OperatorRuntimeABC):
    op: OperatorRuntimeABC
    factor: complex

    @property
    def n_sites(self) -> int:
        return self.op.n_sites

    @staticmethod
    def mat(factor, adjoint: bool):
        if adjoint:
            return [np.conj(factor), 0, 0, factor]
        else:
            return [factor, 0, 0, factor]

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        self.op.apply(*qubits, adjoint=adjoint)

        # NOTE: when applying to multiple qubits, we "spread" the factor evenly
        applied_factor = self.factor ** (1.0 / len(qubits))
        for qbit in qubits:
            if not qbit.is_active():
                continue

            # NOTE: just factor * eye(2)
            m = self.mat(applied_factor, adjoint)

            # TODO: output seems to always be normalized -- no-op?
            qbit.sim_reg.mtrx(m, qbit.addr)

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit, ...],
        adjoint: bool = False,
    ) -> None:

        ctrls: list[int] = []
        for qbit in controls:
            if not qbit.is_active():
                return

            ctrls.append(qbit.addr)

        self.op.control_apply(controls=controls, targets=targets, adjoint=adjoint)

        applied_factor = self.factor ** (1.0 / len(targets))
        for target in targets:
            m = self.mat(applied_factor, adjoint=adjoint)
            target.sim_reg.mcmtrx(ctrls, m, target.addr)


@dataclass(frozen=True)
class MtrxOpRuntime(OperatorRuntimeABC):
    def mat(self, adjoint: bool) -> list[complex]:
        raise NotImplementedError("Override this method in the subclass!")

    @property
    def n_sites(self) -> int:
        # NOTE: pyqrack only supports 2x2 matrices, i.e. single qubit applications
        return 1

    def apply(self, target: PyQrackQubit, adjoint: bool = False) -> None:
        if not target.is_active():
            return

        m = self.mat(adjoint=adjoint)
        target.sim_reg.mtrx(m, target.addr)

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit, ...],
        adjoint: bool = False,
    ) -> None:
        target = targets[0]
        if not target.is_active():
            return

        ctrls: list[int] = []
        for qbit in controls:
            if not qbit.is_active():
                return

            ctrls.append(qbit.addr)

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

    @property
    def n_sites(self) -> int:
        return 1

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

    def apply(self, target: PyQrackQubit, adjoint: bool = False) -> None:
        if not target.is_active():
            return

        sign = (-1) ** adjoint
        angle = sign * self.angle
        target.sim_reg.r(self.pyqrack_axis, angle, target.addr)

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit, ...],
        adjoint: bool = False,
    ) -> None:
        target = targets[0]
        if not target.is_active():
            return

        ctrls: list[int] = []
        for qbit in controls:
            if not qbit.is_active():
                return

            ctrls.append(qbit.addr)

        sign = (-1) ** (not adjoint)
        angle = sign * self.angle
        target.sim_reg.mcr(self.pyqrack_axis, angle, ctrls, target.addr)


@dataclass(frozen=True)
class AdjointRuntime(OperatorRuntimeABC):
    op: OperatorRuntimeABC

    @property
    def n_sites(self) -> int:
        return self.op.n_sites

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        # NOTE: to account for adjoint(adjoint(op))
        passed_on_adjoint = not adjoint

        self.op.apply(*qubits, adjoint=passed_on_adjoint)

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit, ...],
        adjoint: bool = False,
    ) -> None:
        passed_on_adjoint = not adjoint
        self.op.control_apply(
            controls=controls, targets=targets, adjoint=passed_on_adjoint
        )


@dataclass(frozen=True)
class U3Runtime(OperatorRuntimeABC):
    theta: float
    phi: float
    lam: float

    @property
    def n_sites(self) -> int:
        return 1

    def angles(self, adjoint: bool) -> tuple[float, float, float]:
        if adjoint:
            # NOTE: adjoint(U(theta, phi, lam)) == U(-theta, -lam, -phi)
            return -self.theta, -self.lam, -self.phi
        else:
            return self.theta, self.phi, self.lam

    def apply(self, target: PyQrackQubit, adjoint: bool = False) -> None:
        if not target.is_active():
            return

        angles = self.angles(adjoint=adjoint)
        target.sim_reg.u(target.addr, *angles)

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit, ...],
        adjoint: bool = False,
    ) -> None:
        target = targets[0]
        if not target.is_active():
            return

        ctrls: list[int] = []
        for qbit in controls:
            if not qbit.is_active():
                return

            ctrls.append(qbit.addr)

        angles = self.angles(adjoint=adjoint)
        target.sim_reg.mcu(ctrls, target.addr, *angles)


@dataclass(frozen=True)
class PauliStringRuntime(OperatorRuntimeABC):
    string: str
    ops: list[OperatorRuntime]

    @property
    def n_sites(self) -> int:
        return sum((op.n_sites for op in self.ops))

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False):
        if len(qubits) != self.n_sites:
            raise RuntimeError(
                f"Cannot apply Pauli string {self.string} to {len(qubits)} qubits! Make sure the number of qubits matches."
            )

        qubit_index = 0
        for op in self.ops:
            next_qubit_index = qubit_index + op.n_sites
            op.apply(*qubits[qubit_index:next_qubit_index], adjoint=adjoint)
            qubit_index = next_qubit_index

    def control_apply(
        self,
        controls: tuple[PyQrackQubit, ...],
        targets: tuple[PyQrackQubit, ...],
        adjoint: bool = False,
    ) -> None:
        if len(targets) != self.n_sites:
            raise RuntimeError(
                f"Cannot apply Pauli string {self.string} to {len(targets)} qubits! Make sure the number of qubits matches."
            )

        for i, op in enumerate(self.ops):
            # NOTE: this is fine as the size of each op is actually just 1 by definition
            target = targets[i]
            op.control_apply(controls=controls, targets=(target,))
