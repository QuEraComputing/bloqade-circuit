import numpy as np
from kirin import interp
from kirin.lattice import EmptyLattice
from kirin.analysis import const
from kirin.dialects import scf
from kirin.dialects.scf import For, Yield, IfElse

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
        current_gate_fidelity = interp._current_gate_fidelity
        current_atom_survival = interp._current_atom_survival_probability

        for s in stmt.then_body.stmts():
            stmt_impl = interp.lookup_registry(frame=frame, stmt=s)
            if stmt_impl is None:
                continue

            stmt_impl(interp=interp, frame=frame, stmt=s)

        then_gate_fidelity = interp._current_gate_fidelity
        then_atom_survival = interp._current_atom_survival_probability

        # NOTE: reset fidelity of interp to check if the else body results in a worse fidelity
        interp._current_gate_fidelity = current_gate_fidelity
        interp._current_atom_survival_probability = current_atom_survival

        for s in stmt.else_body.stmts():
            stmt_impl = interp.lookup_registry(frame=frame, stmt=s)
            if stmt_impl is None:
                continue

            stmt_impl(interp=interp, frame=frame, stmt=s)

        else_gate_fidelity = interp._current_gate_fidelity
        else_atom_survival = interp._current_atom_survival_probability

        # NOTE: look for the "worse" branch
        then_combined_fidelity = then_gate_fidelity * np.prod(then_atom_survival)
        else_combined_fidelity = else_gate_fidelity * np.prod(else_atom_survival)

        if then_combined_fidelity < else_combined_fidelity:
            interp._current_gate_fidelity = then_gate_fidelity
            interp._current_atom_survival_probability = then_atom_survival
        else:
            interp._current_gate_fidelity = else_gate_fidelity
            interp._current_atom_survival_probability = else_atom_survival

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

        for _ in hint.data:
            for s in stmt.body.stmts():
                interp.eval_stmt(frame=frame, stmt=s)
