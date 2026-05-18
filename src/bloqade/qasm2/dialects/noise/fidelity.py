from kirin import interp
from kirin.analysis import ForwardFrame

from bloqade.analysis.address import Address, AddressReg
from bloqade.analysis.fidelity import FidelityAnalysis

from .stmts import PauliChannel, CZPauliChannel, AtomLossChannel
from ._dialect import dialect


@dialect.register(key="circuit.fidelity")
class FidelityMethodTable(interp.MethodTable):

    @interp.impl(PauliChannel)
    def pauli_channel(
        self,
        interp_: FidelityAnalysis,
        frame: ForwardFrame[Address],
        stmt: PauliChannel,
    ):
        (ps,) = stmt.probabilities
        fidelity = 1 - sum(ps)

        addresses = frame.get(stmt.qargs)

        if not isinstance(addresses, AddressReg):
            return ()

        interp_.update_fidelities(interp_.gate_fidelities, fidelity, addresses)

        return ()

    @interp.impl(CZPauliChannel)
    def cz_pauli_channel(
        self,
        interp_: FidelityAnalysis,
        frame: ForwardFrame[Address],
        stmt: CZPauliChannel,
    ):
        ps_ctrl, ps_target = stmt.probabilities

        fidelity_ctrl = 1 - sum(ps_ctrl)
        fidelity_target = 1 - sum(ps_target)

        addresses_ctrl = frame.get(stmt.ctrls)
        addresses_target = frame.get(stmt.qargs)

        if not isinstance(addresses_ctrl, AddressReg) or not isinstance(
            addresses_target, AddressReg
        ):
            return ()

        interp_.update_fidelities(
            interp_.gate_fidelities, fidelity_ctrl, addresses_ctrl
        )
        interp_.update_fidelities(
            interp_.gate_fidelities, fidelity_target, addresses_target
        )

        return ()

    @interp.impl(AtomLossChannel)
    def atom_loss(
        self,
        interp_: FidelityAnalysis,
        frame: ForwardFrame[Address],
        stmt: AtomLossChannel,
    ):
        addresses = frame.get(stmt.qargs)

        if not isinstance(addresses, AddressReg):
            return ()

        fidelity = 1 - stmt.prob
        interp_.update_fidelities(
            interp_.qubit_survival_fidelities, fidelity, addresses
        )

        return ()
