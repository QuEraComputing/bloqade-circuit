"""Override scf.For constprop with early termination for converged loops.

Kirin's default scf.For constprop iterates the loop body N times for
range(N). For REPEAT-eligible loops where the body is identical each
iteration, this is redundant — the analysis converges after 1-2 iterations.

This module patches the scf dialect's constprop method table to add
early termination, avoiding O(N) analysis time for large loop counts.
"""

from collections.abc import Iterable

from kirin import interp
from kirin.analysis import const
from kirin.dialects.scf.stmts import For
from kirin.dialects.scf._dialect import dialect
from kirin.dialects.scf.constprop import DialectConstProp


class _ScfConstPropWithEarlyTermination(DialectConstProp):

    @interp.impl(For)
    def for_loop(self, interp_: const.Propagate, frame: const.Frame, stmt: For):
        iterable = frame.get(stmt.iterable)
        if isinstance(iterable, const.Value):
            return self._prop_const_iterable_forloop(interp_, frame, stmt, iterable)
        else:
            return tuple(interp_.lattice.top() for _ in stmt.results)

    def _prop_const_iterable_forloop(
        self,
        interp_: const.Propagate,
        frame: const.Frame,
        stmt: For,
        iterable: const.Value,
    ):
        frame_is_not_pure = False
        if not isinstance(iterable.data, Iterable):
            raise interp.InterpreterError(
                f"Expected iterable, got {type(iterable.data)}"
            )

        loop_vars = frame.get_values(stmt.initializers)

        prev_loop_vars = None
        for value in iterable.data:
            with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
                loop_vars = interp_.frame_call_region(
                    body_frame, stmt, stmt.body, const.Value(value), *loop_vars
                )

            if body_frame.frame_is_not_pure:
                frame_is_not_pure = True
            if loop_vars is None:
                loop_vars = ()
            elif isinstance(loop_vars, interp.ReturnValue):
                return loop_vars

            # Early termination: if loop variables converge between iterations,
            # stop iterating instead of running all N iterations of range(N).
            if prev_loop_vars is not None and loop_vars == prev_loop_vars:
                break
            prev_loop_vars = loop_vars

        if not frame_is_not_pure:
            frame.should_be_pure.add(stmt)
        return loop_vars


def install():
    """Patch the scf dialect's constprop to use early termination."""
    dialect.interps["constprop"] = _ScfConstPropWithEarlyTermination()
