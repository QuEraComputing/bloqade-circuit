import cirq
from kirin.emit import EmitError
from kirin.interp import MethodTable, impl

from ... import noise
from .runtime import (
    KronRuntime,
    BasicOpRuntime,
    OperatorRuntimeABC,
    PauliStringRuntime,
)
from .emit_circuit import EmitCirq, EmitCirqFrame


@noise.dialect.register(key="emit.cirq")
class EmitCirqNoiseMethods(MethodTable):

    @impl(noise.stmts.StochasticUnitaryChannel)
    def stochastic_unitary_channel(
        self,
        emit: EmitCirq,
        frame: EmitCirqFrame,
        stmt: noise.stmts.StochasticUnitaryChannel,
    ):
        ops = frame.get(stmt.operators)
        ps = frame.get(stmt.probabilities)

        error_probabilities = {self._op_to_key(op_): p for op_, p in zip(ops, ps)}
        cirq_op = cirq.asymmetric_depolarize(error_probabilities=error_probabilities)
        return (BasicOpRuntime(cirq_op),)

    @staticmethod
    def _op_to_key(operator: OperatorRuntimeABC) -> str:
        match operator:
            case KronRuntime():
                key_lhs = EmitCirqNoiseMethods._op_to_key(operator.lhs)
                key_rhs = EmitCirqNoiseMethods._op_to_key(operator.rhs)
                return key_lhs + key_rhs

            case BasicOpRuntime():
                return str(operator.gate)

            case PauliStringRuntime():
                return operator.string

            case _:
                raise EmitError(
                    f"Unexpected operator runtime in StochasticUnitaryChannel of type {type(operator).__name__} encountered!"
                )
