import cirq
from kirin.interp import MethodTable, impl, InterpreterError

from bloqade.squin import noise

from .base import EmitCirq, EmitCirqFrame
from .runtime import (
    KronRuntime,
    BasicOpRuntime,
    OperatorRuntimeABC,
    PauliStringRuntime,
)


@noise.dialect.register(key="emit.cirq")
class EmitCirqNoiseMethods(MethodTable):

    @impl(noise.stmts.Depolarize)
    def depolarize(
        self, interp: EmitCirq, frame: EmitCirqFrame, stmt: noise.stmts.Depolarize
    ):
        p = frame.get(stmt.p)
        gate = cirq.depolarize(p, n_qubits=1)
        return (BasicOpRuntime(gate=gate),)

    @impl(noise.stmts.Depolarize2)
    def depolarize2(
        self, interp: EmitCirq, frame: EmitCirqFrame, stmt: noise.stmts.Depolarize2
    ):
        p = frame.get(stmt.p)
        gate = cirq.depolarize(p, n_qubits=2)
        return (BasicOpRuntime(gate=gate),)

    @impl(noise.stmts.SingleQubitPauliChannel)
    def single_qubit_pauli_channel(
        self,
        interp: EmitCirq,
        frame: EmitCirqFrame,
        stmt: noise.stmts.SingleQubitPauliChannel,
    ):
        ps = frame.get(stmt.params)
        gate = cirq.asymmetric_depolarize(*ps)
        return (BasicOpRuntime(gate=gate),)

    @impl(noise.stmts.TwoQubitPauliChannel)
    def two_qubit_pauli_channel(
        self,
        interp: EmitCirq,
        frame: EmitCirqFrame,
        stmt: noise.stmts.TwoQubitPauliChannel,
    ):
        ps = frame.get(stmt.params)
        paulis = ("I", "X", "Y", "Z")
        pauli_combinations = [
            pauli1 + pauli2
            for pauli1 in paulis
            for pauli2 in paulis
            if not (pauli1 == pauli2 == "I")
        ]
        error_probabilities = {key: p for (key, p) in zip(pauli_combinations, ps)}
        gate = cirq.asymmetric_depolarize(error_probabilities=error_probabilities)
        return (BasicOpRuntime(gate),)

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
                raise InterpreterError(
                    f"Unexpected operator runtime in StochasticUnitaryChannel of type {type(operator).__name__} encountered!"
                )
