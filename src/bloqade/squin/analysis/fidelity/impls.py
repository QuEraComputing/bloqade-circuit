from typing import TypeVar, cast

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
        parent_stmt = frame.parent_stmt or stmt
        px = interp_.get_const(parent_stmt, stmt.px)
        py = interp_.get_const(parent_stmt, stmt.py)
        pz = interp_.get_const(parent_stmt, stmt.pz)

        # if any((px is None, py is None, pz is None)):
        #     return

        addresses = interp_.get_address(parent_stmt, stmt.qubits)
        assert isinstance(addresses, AddressReg)

        fidelity = cast(float, 1 - (px + py + pz))  # type: ignore -- NOTE: the linter doesn't understand the above if
        frame.update_fidelities(fidelity, addresses)

        return ()
