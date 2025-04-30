from kirin import interp
from kirin.lattice import EmptyLattice
from kirin.dialects.scf import dialect as scf
from kirin.dialects.scf.stmts import IfElse

from .analysis import FidelityAnalysis


@scf.register(key="circuit.fidelity")
class ScfFidelityMethodTable(interp.MethodTable):

    @interp.impl(IfElse)
    def if_else(
        self,
        interp: FidelityAnalysis,
        frame: interp.Frame[EmptyLattice],
        stmt: IfElse,
    ):
        # NOTE: store current fidelity for later
        current_fidelity = interp.current_fidelity

        for s in stmt.then_body.stmts():
            stmt_impl = interp.lookup_registry(frame=frame, stmt=s)
            if stmt_impl is None:
                continue

            stmt_impl(interp=interp, frame=frame, stmt=s)

        then_fidelity = interp.current_fidelity

        # NOTE: reset fidelity of interp to check if the else body results in a worse fidelity
        interp.current_fidelity = current_fidelity

        for s in stmt.else_body.stmts():
            stmt_impl = interp.lookup_registry(frame=frame, stmt=s)
            if stmt_impl is None:
                continue

            stmt_impl(interp=interp, frame=frame, stmt=s)

        else_fidelity = interp.current_fidelity

        if then_fidelity < else_fidelity:
            interp.current_fidelity = then_fidelity
        else:
            interp.current_fidelity = else_fidelity
