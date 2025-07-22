import math
from typing import Sequence
from numbers import Number
from dataclasses import dataclass

import cirq
from kirin.emit import EmitError


@dataclass
class OperatorRuntimeABC:
    def num_qubits(self) -> int: ...

    def apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        if self.num_qubits() == len(qubits):
            return self.unsafe_apply(qubits, adjoint=adjoint)

        if self.num_qubits() == 1:
            ops = []
            for qbit in qubits:
                ops.extend(self.apply([qbit], adjoint=adjoint))
            return ops

        raise EmitError(
            f"Cannot apply operator of size {self.num_qubits()} to {len(qubits)} qubits!"
        )

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        raise NotImplementedError(
            f"Apply method needs to be implemented in {self.__class__.__name__}"
        )


@dataclass
class BasicOpRuntime(OperatorRuntimeABC):
    gate: cirq.Gate

    def num_qubits(self) -> int:
        return self.gate.num_qubits()

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        return [self.gate(*qubits)]


@dataclass
class UnitaryRuntime(BasicOpRuntime):
    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        exponent = (-1) ** adjoint
        return [self.gate(*qubits) ** exponent]


@dataclass
class HermitianRuntime(BasicOpRuntime):
    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        return [self.gate(*qubits)]


@dataclass
class ProjectorRuntime(OperatorRuntimeABC):
    target_state: bool

    def num_qubits(self) -> int:
        return 1

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        # NOTE: this doesn't scale well, but works
        sign = (-1) ** self.target_state
        p = (1 + sign * cirq.Z(*qubits)) / 2
        return [p]


@dataclass
class SpRuntime(OperatorRuntimeABC):
    def num_qubits(self) -> int:
        return 1

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        if adjoint:
            return SnRuntime().unsafe_apply(qubits, adjoint=False)

        return [(cirq.X(*qubits) - 1j * cirq.Y(*qubits)) / 2]  # type: ignore  -- we're not dealing with cirq's type issues


@dataclass
class SnRuntime(OperatorRuntimeABC):
    def num_qubits(self) -> int:
        return 1

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        if adjoint:
            return SpRuntime().unsafe_apply(qubits, adjoint=False)

        return [(cirq.X(*qubits) + 1j * cirq.Y(*qubits)) / 2]  # type: ignore  -- we're not dealing with cirq's type issues


@dataclass
class MultRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def num_qubits(self) -> int:
        n = self.lhs.num_qubits()
        assert n == self.rhs.num_qubits()
        return n

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        rhs = self.rhs.unsafe_apply(qubits, adjoint=adjoint)
        lhs = self.lhs.unsafe_apply(qubits, adjoint=adjoint)

        if adjoint:
            return lhs + rhs
        else:
            return rhs + lhs


@dataclass
class KronRuntime(OperatorRuntimeABC):
    lhs: OperatorRuntimeABC
    rhs: OperatorRuntimeABC

    def num_qubits(self) -> int:
        return self.lhs.num_qubits() + self.rhs.num_qubits()

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        n = self.lhs.num_qubits()
        cirq_ops = self.lhs.unsafe_apply(qubits[:n], adjoint=adjoint)
        cirq_ops.extend(self.rhs.unsafe_apply(qubits[n:], adjoint=adjoint))
        return cirq_ops


@dataclass
class ControlRuntime(OperatorRuntimeABC):
    operator: OperatorRuntimeABC
    n_controls: int

    def num_qubits(self) -> int:
        return self.n_controls + self.operator.num_qubits()

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        m = len(qubits) - self.n_controls
        cirq_ops = self.operator.unsafe_apply(qubits[m:], adjoint=adjoint)
        controlled_ops = [cirq_op.controlled_by(*qubits[:m]) for cirq_op in cirq_ops]
        return controlled_ops


@dataclass
class AdjointRuntime(OperatorRuntimeABC):
    operator: OperatorRuntimeABC

    def num_qubits(self) -> int:
        return self.operator.num_qubits()

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        # NOTE: to account for e.g. adjoint(adjoint(op))
        passed_on_adjoint = not adjoint
        return self.operator.unsafe_apply(qubits, adjoint=passed_on_adjoint)


@dataclass
class U3Runtime(OperatorRuntimeABC):
    theta: float
    phi: float
    lam: float

    def num_qubits(self) -> int:
        return 1

    def angles(self, adjoint: bool) -> tuple[float, float, float]:
        if adjoint:
            # NOTE: adjoint(U(theta, phi, lam)) == U(-theta, -lam, -phi)
            return -self.theta, -self.lam, -self.phi
        else:
            return self.theta, self.phi, self.lam

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        theta, phi, lam = self.angles(adjoint=adjoint)

        ops = [
            cirq.Rz(rads=lam)(*qubits),
            cirq.Rx(rads=math.pi / 2)(*qubits),
            cirq.Rz(rads=theta)(*qubits),
            cirq.Rx(rads=-math.pi / 2)(*qubits),
            cirq.Rz(rads=phi)(*qubits),
        ]

        return ops


@dataclass
class ScaleRuntime(OperatorRuntimeABC):
    factor: Number
    operator: OperatorRuntimeABC

    def num_qubits(self) -> int:
        return self.operator.num_qubits()

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        cirq_ops = self.operator.unsafe_apply(qubits=qubits, adjoint=adjoint)
        return [self.factor * cirq_ops[0]] + cirq_ops[1:]  # type: ignore


@dataclass
class PauliStringRuntime(OperatorRuntimeABC):
    string: str

    def num_qubits(self) -> int:
        return len(self.string)

    def unsafe_apply(
        self, qubits: Sequence[cirq.Qid], adjoint: bool = False
    ) -> list[cirq.Operation]:
        pauli_mapping = {
            qbit: pauli_label for (qbit, pauli_label) in zip(qubits, self.string)
        }
        return [cirq.PauliString(pauli_mapping)]
