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
        frame.update_fidelities(fidelity, addresses)

        return ()

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
        frame.update_fidelities(fidelity, addresses)

        return ()
