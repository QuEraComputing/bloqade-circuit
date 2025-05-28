import random
import typing
from dataclasses import dataclass

from kirin import interp
from kirin.dialects import ilist

from bloqade.pyqrack import QubitState, PyQrackQubit, PyQrackInterpreter
from bloqade.squin.noise.stmts import QubitLoss, StochasticUnitaryChannel
from bloqade.squin.noise._dialect import dialect as squin_noise_dialect

from ..runtime import OperatorRuntimeABC


@dataclass(frozen=True)
class StochasticUnitaryChannelRuntime(OperatorRuntimeABC):
    operators: ilist.IList[OperatorRuntimeABC, typing.Any]
    probabilities: ilist.IList[float, typing.Any]

    @property
    def n_sites(self) -> int:
        n = self.operators[0].n_sites
        for op in self.operators[1:]:
            assert (
                op.n_sites == n
            ), "Encountered a stochastic unitary channel with operators of different size!"
        return n

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        # NOTE: probabilities don't necessarily sum to 1; could be no noise event should occur
        p_no_op = 1 - sum(self.probabilities)
        if random.uniform(0.0, 1.0) < p_no_op:
            return

        selected_ops = random.choices(self.operators, weights=self.probabilities)
        for op in selected_ops:
            op.apply(*qubits, adjoint=adjoint)


@dataclass(frozen=True)
class QubitLossRuntime(OperatorRuntimeABC):
    p: float

    @property
    def n_sites(self) -> int:
        return 1

    def apply(self, qubit: PyQrackQubit, adjoint: bool = False) -> None:
        if random.uniform(0.0, 1.0) < self.p:
            qubit.state = QubitState.Lost


@squin_noise_dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):
    @interp.impl(StochasticUnitaryChannel)
    def stochastic_unitary_channel(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: StochasticUnitaryChannel,
    ):
        operators = frame.get(stmt.operators)
        probabilities = frame.get(stmt.probabilities)

        return (StochasticUnitaryChannelRuntime(operators, probabilities),)

    @interp.impl(QubitLoss)
    def qubit_loss(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: QubitLoss
    ):
        p = frame.get(stmt.p)
        return (QubitLossRuntime(p),)
