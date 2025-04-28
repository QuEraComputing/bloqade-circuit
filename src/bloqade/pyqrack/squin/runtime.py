from dataclasses import dataclass

import numpy as np

from bloqade.pyqrack import PyQrackQubit


@dataclass
class OperatorRuntimeABC:
    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        raise NotImplementedError(
            "Operator runtime base class should not be called directly, override the method"
        )

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        raise NotImplementedError(f"Can't apply controlled version of {self}")


@dataclass
class OperatorRuntime(OperatorRuntimeABC):
    method_name: str

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        method_name = self.method_name
        if adjoint:
            method_name = "adj" + method_name
        getattr(qubits[0].sim_reg, method_name)(qubits[0].addr)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        ctrls = [qbit.addr for qbit in qubits[:-1]]
        target = qubits[-1]
        method_name = "mc"
        if adjoint:
            method_name += "adj"
        method_name += self.method_name
        getattr(target.sim_reg, method_name)(target.addr, ctrls)


@dataclass
class ControlRuntime(OperatorRuntimeABC):
    op: OperatorRuntimeABC
    n_controls: int

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        # NOTE: this is a bit odd, since you can "skip" qubits by making n_controls < len(qubits)
        ctrls = qubits[: self.n_controls]
        target = qubits[-1]
        self.op.control_apply(target, *ctrls, adjoint=adjoint)


@dataclass
class ProjectorRuntime(OperatorRuntimeABC):
    to_state: bool

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        qubits[0].sim_reg.force_m(qubits[0].addr, self.to_state)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        m = [not self.to_state, 0, 0, self.to_state]
        target = qubits[-1]
        ctrls = [qbit.addr for qbit in qubits[:-1]]
        target.sim_reg.mcmtrx(ctrls, m, target.addr)


@dataclass
class IdentityRuntime(OperatorRuntimeABC):
    # TODO: do we even need sites? The apply never does anything
    sites: int

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        pass

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        pass


@dataclass
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


@dataclass
class KronRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        self.lhs.apply(qubits[0], adjoint=adjoint)
        self.rhs.apply(qubits[1], adjoint=adjoint)


@dataclass
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


@dataclass
class AdjointRuntime(OperatorRuntimeABC):
    op: OperatorRuntimeABC

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = True) -> None:
        self.op.apply(*qubits, adjoint=adjoint)

    def control_apply(self, *qubits: PyQrackQubit, adjoint: bool = True) -> None:
        self.op.control_apply(*qubits, adjoint=adjoint)
