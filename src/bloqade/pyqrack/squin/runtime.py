from dataclasses import dataclass

from bloqade.pyqrack import PyQrackQubit


@dataclass
class OperatorRuntimeABC:
    def apply(self, *qubits: PyQrackQubit) -> None:
        raise NotImplementedError(
            "Operator runtime base class should not be called directly, override the method"
        )


@dataclass
class OperatorRuntime(OperatorRuntimeABC):
    method_name: str

    def apply(self, *qubits: PyQrackQubit) -> None:
        getattr(qubits[0].sim_reg, self.method_name)(qubits[0].addr)


@dataclass
class ControlRuntime(OperatorRuntimeABC):
    method_name: str
    n_controls: int

    def apply(self, *qubits: PyQrackQubit) -> None:
        # NOTE: this is a bit odd, since you can "skip" qubits by making n_controls < len(qubits)
        ctrls = [qbit.addr for qbit in qubits[: self.n_controls]]
        target = qubits[-1]
        getattr(target.sim_reg, self.method_name)(ctrls, target.addr)


@dataclass
class ProjectorRuntime(OperatorRuntimeABC):
    to_state: bool

    def apply(self, *qubits: PyQrackQubit) -> None:
        qubits[-1].sim_reg.force_m(qubits[-1].addr, self.to_state)


@dataclass
class IdentityRuntime(OperatorRuntimeABC):
    # TODO: do we even need sites? The apply never does anything
    sites: int

    def apply(self, *qubits: PyQrackQubit) -> None:
        pass


@dataclass
class MultRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def apply(self, *qubits: PyQrackQubit) -> None:
        self.rhs.apply(*qubits)
        self.lhs.apply(*qubits)


@dataclass
class KronRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def apply(self, *qubits: PyQrackQubit) -> None:
        self.lhs.apply(qubits[0])
        self.rhs.apply(qubits[1])


@dataclass
class ScaleRuntime(OperatorRuntimeABC):
    op: OperatorRuntimeABC
    factor: complex

    def apply(self, *qubits: PyQrackQubit) -> None:
        target = qubits[0]
        self.op.apply(target)

        # NOTE: just factor * eye(2)
        mat = [self.factor, 0, 0, self.factor]

        # TODO: output seems to always be normalized -- no-op?
        target.sim_reg.mtrx(mat, target.addr)
