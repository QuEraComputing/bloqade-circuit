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

        defaults = interp_.default_probabilities.get(stmt.name, (None,) * 3)
        px = frame.const_values.get(stmt.px, defaults[0])
        py = frame.const_values.get(stmt.py, defaults[1])
        pz = frame.const_values.get(stmt.pz, defaults[2])

        if any((px is None, py is None, pz is None)):
            return

        addresses = frame.current_addresses.get(stmt.qubits)
        assert isinstance(addresses, AddressReg)

        fidelity = cast(float, 1 - (px + py + pz))  # type: ignore -- NOTE: the linter doesn't understand the above if
        print(fidelity)
        frame.update_fidelities(fidelity, addresses)

        return ()
