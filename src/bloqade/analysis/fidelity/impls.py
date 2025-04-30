from kirin import interp
from kirin.lattice import EmptyLattice
from kirin.analysis import const
from kirin.dialects import scf
from kirin.dialects.scf.stmts import For, Yield, IfElse

from .analysis import FidelityAnalysis


@scf.dialect.register(key="circuit.fidelity")
class ScfFidelityMethodTable(interp.MethodTable):

    @interp.impl(IfElse)
    def if_else(
        self,
        interp: FidelityAnalysis,
        frame: interp.Frame[EmptyLattice],
        stmt: IfElse,
    ):
        # NOTE: store current fidelity for later
        current_fidelity = interp._current_gate_fidelity

        for s in stmt.then_body.stmts():
            stmt_impl = interp.lookup_registry(frame=frame, stmt=s)
            if stmt_impl is None:
                continue

            stmt_impl(interp=interp, frame=frame, stmt=s)

        then_fidelity = interp._current_gate_fidelity

        # NOTE: reset fidelity of interp to check if the else body results in a worse fidelity
        interp._current_gate_fidelity = current_fidelity

        for s in stmt.else_body.stmts():
            stmt_impl = interp.lookup_registry(frame=frame, stmt=s)
            if stmt_impl is None:
                continue

            stmt_impl(interp=interp, frame=frame, stmt=s)

        else_fidelity = interp._current_gate_fidelity

        if then_fidelity < else_fidelity:
            interp._current_gate_fidelity = then_fidelity
        else:
            interp._current_gate_fidelity = else_fidelity

    @interp.impl(Yield)
    def yield_(
        self, interp: FidelityAnalysis, frame: interp.Frame[EmptyLattice], stmt: Yield
    ):
        # NOTE: yield can by definition only contain values, never any stmts, so fidelity cannot decrease
        return

    @interp.impl(For)
    def for_loop(
        self, interp: FidelityAnalysis, frame: interp.Frame[EmptyLattice], stmt: For
    ):

        if not isinstance(hint := stmt.iterable.hints.get("const"), const.Value):
            # NOTE: not clear how long this loop is
            # TODO: should we at least count the body once?
            return

        current_fidelity = interp._current_gate_fidelity

        # NOTE: we reset the interpreter fidelity and evaluate the fidelity for the body only once
        interp._current_gate_fidelity = 1.0
        for s in stmt.body.stmts():
            stmt_impl = interp.lookup_registry(frame=frame, stmt=s)
            if stmt_impl is None:
                continue

            stmt_impl(interp=interp, frame=frame, stmt=s)

        # NOTE: reset current fidelity now in case of 0 iterations
        loop_body_fidelity = interp._current_gate_fidelity
        interp._current_gate_fidelity = current_fidelity

        # NOTE: now we simply decrease the fidelity according to the number of iterations
        iterable = hint.data
        for _ in iterable:
            interp._current_gate_fidelity *= loop_body_fidelity
