from typing import TypeVar

from kirin import interp

from bloqade.squin import noise
from bloqade.analysis.address import AddressReg
from bloqade.analysis.fidelity import FidelityFrame, FidelityAnalysis

T = TypeVar("T")


@noise.dialect.register(key="circuit.fidelity")
class __NoiseMethods(interp.MethodTable):

    @interp.impl(noise.stmts.SingleQubitPauliChannel)
    def single_qubit_pauli_channel(
        self,
        interp_: FidelityAnalysis,
        frame: FidelityFrame,
        stmt: noise.stmts.SingleQubitPauliChannel,
    ):
        px = interp_.get_const(frame, stmt, stmt.px)
        py = interp_.get_const(frame, stmt, stmt.py)
        pz = interp_.get_const(frame, stmt, stmt.pz)

        addresses = interp_.get_address(frame, stmt, stmt.qubits)
        assert isinstance(addresses, AddressReg)

        fidelity = 1 - (px + py + pz)
        frame.update_gate_fidelities(interp_.qubit_count, fidelity, addresses)

        return ()

    @interp.impl(noise.stmts.TwoQubitPauliChannel)
    def two_qubit_pauli_channel(
        self,
        interp_: FidelityAnalysis,
        frame: FidelityFrame,
        stmt: noise.stmts.TwoQubitPauliChannel,
    ):
        stmt.probabilities
        raise NotImplementedError("TODO")

    @interp.impl(noise.stmts.Depolarize)
    def depolarize(
        self,
        interp_: FidelityAnalysis,
        frame: FidelityFrame,
        stmt: noise.stmts.Depolarize,
    ):
        p = interp_.get_const(frame, stmt, stmt.p)

        addresses = interp_.get_address(frame, stmt, stmt.qubits)
        assert isinstance(addresses, AddressReg)

        fidelity = 1 - p
        frame.update_gate_fidelities(interp_.qubit_count, fidelity, addresses)

        return ()

    @interp.impl(noise.stmts.Depolarize2)
    def depolarize2(
        self,
        interp_: FidelityAnalysis,
        frame: FidelityFrame,
        stmt: noise.stmts.Depolarize2,
    ):
        stmt.p
        raise NotImplementedError("TODO")

    @interp.impl(noise.stmts.QubitLoss)
    def qubit_loss(
        self,
        interp_: FidelityAnalysis,
        frame: FidelityFrame,
        stmt: noise.stmts.QubitLoss,
    ):
        p = interp_.get_const(frame, stmt, stmt.p)
        survival = 1 - p

        addresses = interp_.get_address(frame, stmt, stmt.qubits)
        assert isinstance(addresses, AddressReg)

        frame.update_survival_fidelities(interp_.qubit_count, survival, addresses)
