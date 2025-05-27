from kirin import interp
from kirin.lattice import EmptyLattice

from bloqade.analysis.address import AddressQubit, AddressTuple
from bloqade.analysis.fidelity import FidelityAnalysis

from .stmts import PauliChannel, CZPauliChannel, AtomLossChannel
from ._dialect import dialect


@dialect.register(key="circuit.fidelity")
class FidelityMethodTable(interp.MethodTable):

    @interp.impl(PauliChannel)
    @interp.impl(CZPauliChannel)
    def pauli_channel(
        self,
        interp: FidelityAnalysis,
        frame: interp.Frame[EmptyLattice],
        stmt: PauliChannel | CZPauliChannel,
    ):
        probs = stmt.probabilities
        try:
            ps, ps_ctrl = probs
        except ValueError:
            (ps,) = probs
            ps_ctrl = ()

        p = sum(ps)
        p_ctrl = sum(ps_ctrl)

        # NOTE: fidelity is just the inverse probability of any noise to occur
        fid = (1 - p) * (1 - p_ctrl)

        interp._current_gate_fidelity *= fid

    @interp.impl(AtomLossChannel)
    def atom_loss(
        self,
        interp: FidelityAnalysis,
        frame: interp.Frame[EmptyLattice],
        stmt: AtomLossChannel,
    ):
        # NOTE: since AtomLossChannel acts on IList[Qubit], we know the assigned address is a tuple
        addresses: AddressTuple = interp.addr_frame.get(stmt.qargs)

        # NOTE: get the corresponding index and reduce survival probability accordingly
        for qbit_address in addresses.data:
            assert isinstance(qbit_address, AddressQubit)
            index = qbit_address.data
            interp._current_atom_survival_probability[index] *= 1 - stmt.prob
