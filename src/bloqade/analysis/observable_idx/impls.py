from kirin import interp
from kirin.lattice import EmptyLattice
from kirin.dialects import scf

from bloqade.decoders.dialects import annotate

from .analysis import ObservableIdxFrame, ObservableIdxAnalysis


@annotate.dialect.register(key="observable_idx")
class _AnnotateMethods(interp.MethodTable):
    @interp.impl(annotate.stmts.SetObservable)
    def set_observable(
        self,
        interp_: ObservableIdxAnalysis,
        frame: ObservableIdxFrame,
        stmt: annotate.stmts.SetObservable,
    ):
        # Assign on first visit so loop fixpoint iteration doesn't shift indices.
        if stmt not in frame.observable_idx_at_stmt:
            frame.observable_idx_at_stmt[stmt] = interp_.observable_count
            interp_.observable_count += 1
        return (EmptyLattice.bottom(),)


@scf.dialect.register(key="observable_idx")
class _ScfMethods(interp.MethodTable):
    """SetObservable can appear inside scf.For bodies and scf.IfElse branches.
    The default Forward fallback doesn't descend into nested regions, so we
    provide explicit single-pass body visits here. The SetObservable impl is
    idempotent (first-visit-only), so we don't iterate to fixpoint."""

    @interp.impl(scf.For)
    def for_loop(
        self,
        interp_: ObservableIdxAnalysis,
        frame: ObservableIdxFrame,
        stmt: scf.For,
    ):
        with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
            loop_vars = frame.get_values(stmt.initializers)
            interp_.frame_call_region(
                body_frame, stmt, stmt.body, EmptyLattice.bottom(), *loop_vars
            )
            for s, idx in body_frame.observable_idx_at_stmt.items():
                frame.observable_idx_at_stmt.setdefault(s, idx)
        return tuple(EmptyLattice.bottom() for _ in stmt.results)

    @interp.impl(scf.IfElse)
    def if_else(
        self,
        interp_: ObservableIdxAnalysis,
        frame: ObservableIdxFrame,
        stmt: scf.IfElse,
    ):
        for body in (stmt.then_body, stmt.else_body):
            with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
                interp_.frame_call_region(body_frame, stmt, body, frame.get(stmt.cond))
                for s, idx in body_frame.observable_idx_at_stmt.items():
                    frame.observable_idx_at_stmt.setdefault(s, idx)
        return tuple(EmptyLattice.bottom() for _ in stmt.results)
