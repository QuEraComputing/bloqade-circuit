import cirq
from kirin.interp import MethodTable, impl

from bloqade.squin import noise

from .base import EmitCirq, EmitCirqFrame


@noise.dialect.register(key="emit.cirq")
class __EmitCirqNoiseMethods(MethodTable):

    two_qubit_paulis = (
        "IX",
        "IY",
        "IZ",
        "XI",
        "XX",
        "XY",
        "XZ",
        "YI",
        "YX",
        "YY",
        "YZ",
        "ZI",
        "ZX",
        "ZY",
        "ZZ",
    )

    @impl(noise.stmts.Depolarize)
    def depolarize(
        self, interp: EmitCirq, frame: EmitCirqFrame, stmt: noise.stmts.Depolarize
    ):
        p = frame.get(stmt.p)
        qubits = frame.get(stmt.qubits)
        cirfq_op = cirq.depolarize(p, n_qubits=1).on_each(qubits)
        interp.circuit.append(cirfq_op)
        return ()

    @impl(noise.stmts.Depolarize2)
    def depolarize2(
        self, interp: EmitCirq, frame: EmitCirqFrame, stmt: noise.stmts.Depolarize2
    ):
        p = frame.get(stmt.p)
        controls = frame.get(stmt.controls)
        targets = frame.get(stmt.targets)
        cirq_qubits = [(ctrl, target) for ctrl, target in zip(controls, targets)]
        cirq_op = cirq.depolarize(p, n_qubits=2).on_each(cirq_qubits)
        interp.circuit.append(cirq_op)
        return ()

    @impl(noise.stmts.SingleQubitPauliChannel)
    def single_qubit_pauli_channel(
        self,
        interp: EmitCirq,
        frame: EmitCirqFrame,
        stmt: noise.stmts.SingleQubitPauliChannel,
    ):
        px = frame.get(stmt.px)
        py = frame.get(stmt.py)
        pz = frame.get(stmt.pz)
        qubits = frame.get(stmt.qubits)

        cirq_op = cirq.asymmetric_depolarize(px, py, pz).on_each(qubits)
        interp.circuit.append(cirq_op)

        return ()

    @impl(noise.stmts.TwoQubitPauliChannel)
    def two_qubit_pauli_channel(
        self,
        interp: EmitCirq,
        frame: EmitCirqFrame,
        stmt: noise.stmts.TwoQubitPauliChannel,
    ):
        ps = frame.get(stmt.probabilities)
        error_probabilities = {
            key: p for (key, p) in zip(self.two_qubit_paulis, ps) if p != 0
        }

        controls = frame.get(stmt.controls)
        targets = frame.get(stmt.targets)
        cirq_qubits = [(ctrl, target) for ctrl, target in zip(controls, targets)]

        cirq_op = cirq.asymmetric_depolarize(
            error_probabilities=error_probabilities
        ).on_each(cirq_qubits)
        interp.circuit.append(cirq_op)

        return ()
