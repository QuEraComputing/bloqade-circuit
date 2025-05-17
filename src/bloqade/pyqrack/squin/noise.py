from kirin import interp

from bloqade.squin import noise
from bloqade.pyqrack import PyQrackInterpreter

from .runtime import StochasticUnitaryChannelRuntime


@noise.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):
    @interp.impl(noise.stmts.Depolarize)
    @interp.impl(noise.stmts.PauliError)
    @interp.impl(noise.stmts.PPError)
    def stochastic_unitary_channel(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: noise.stmts.UnitaryChannel,
    ):
        probabilities = frame.get_values(stmt.probabilities)
        operators = frame.get_values(stmt.operators)
        return (
            StochasticUnitaryChannelRuntime(
                operators=operators, probabilities=probabilities
            ),
        )
