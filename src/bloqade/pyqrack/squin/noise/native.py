import random
import typing
from dataclasses import dataclass

from kirin import interp
from kirin.dialects import ilist

from bloqade.pyqrack import PyQrackQubit, PyQrackInterpreter
from bloqade.squin.noise.stmts import StochasticUnitaryChannel
from bloqade.squin.noise._dialect import dialect as squin_noise_dialect

from ..runtime import OperatorRuntimeABC


@dataclass(frozen=True)
class StochasticUnitaryChannelRuntime(OperatorRuntimeABC):
    operators: ilist.IList[OperatorRuntimeABC, typing.Any]
    probabilities: ilist.IList[float, typing.Any]

    @property
    def n_sites(self) -> int:
        return self.operators[0].n_sites

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        # NOTE: probabilities don't necessarily sum to 1; could be no noise event should occur
        p_no_op = 1 - sum(self.probabilities)
        if random.uniform(0.0, 1.0) < p_no_op:
            return

        selected_ops = random.choices(self.operators, weights=self.probabilities)
        for op in selected_ops:
            op.apply(*qubits, adjoint=adjoint)


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
