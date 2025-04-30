from kirin import interp
from kirin.lattice import EmptyLattice

from bloqade.analysis.fidelity import FidelityAnalysis

from .native import dialect as native
from .native.stmts import PauliChannel, CZPauliChannel


@native.register(key="circuit.fidelity")
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

        interp.current_fidelity *= fid
