import random
import typing
from functools import cached_property
from dataclasses import dataclass

from kirin import interp
from kirin.dialects import ilist

from bloqade.pyqrack import QubitState, PyQrackQubit, PyQrackInterpreter
from bloqade.squin.noise.stmts import (
    QubitLoss,
    Depolarize,
    PauliError,
    Depolarize2,
    TwoQubitPauliChannel,
    SingleQubitPauliChannel,
    StochasticUnitaryChannel,
)
from bloqade.squin.noise._dialect import dialect as squin_noise_dialect

from ..runtime import KronRuntime, IdentityRuntime, OperatorRuntime, OperatorRuntimeABC


@dataclass(frozen=True)
class StochasticUnitaryChannelRuntime(OperatorRuntimeABC):
    operators: typing.Sequence[OperatorRuntimeABC]
    probabilities: ilist.IList[float, typing.Any] | list[float]

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
    @interp.impl(PauliError)
    def pauli_error(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: PauliError
    ):
        op = frame.get(stmt.basis)
        p = frame.get(stmt.p)
        return (StochasticUnitaryChannelRuntime([op], [p]),)

    @interp.impl(Depolarize)
    def depolarize(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: Depolarize
    ):
        p = frame.get(stmt.p)
        ps = [p / 3.0] * 3
        ops = self.single_qubit_paulis
        return (StochasticUnitaryChannelRuntime(ops, ps),)

    @interp.impl(Depolarize2)
    def depolarize2(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: Depolarize2
    ):
        p = frame.get(stmt.p)
        ps = [p / 15.0] * 15
        ops = self.two_qubit_paulis
        return (StochasticUnitaryChannelRuntime(ops, ps),)

    @interp.impl(SingleQubitPauliChannel)
    def single_qubit_pauli_channel(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: SingleQubitPauliChannel,
    ):
        ps = frame.get(stmt.params)
        ops = self.single_qubit_paulis
        return (StochasticUnitaryChannelRuntime(ops, ps),)

    @interp.impl(TwoQubitPauliChannel)
    def two_qubit_pauli_channel(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: TwoQubitPauliChannel,
    ):
        ps = frame.get(stmt.params)
        ops = self.two_qubit_paulis
        return (StochasticUnitaryChannelRuntime(ops, ps),)

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

    @cached_property
    def single_qubit_paulis(self):
        return [OperatorRuntime("x"), OperatorRuntime("y"), OperatorRuntime("z")]

    @cached_property
    def two_qubit_paulis(self):
        paulis = (IdentityRuntime(sites=1), *self.single_qubit_paulis)
        ops: list[KronRuntime] = []
        for idx1, pauli1 in enumerate(paulis):
            for idx2, pauli2 in enumerate(paulis):
                if idx1 == idx2 == 0:
                    # NOTE: 'II'
                    continue

                ops.append(KronRuntime(pauli1, pauli2))

        return ops
