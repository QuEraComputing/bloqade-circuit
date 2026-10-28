"""This module holds the reference analysis rule for the qubit dialect."""

from kirin import interp
from kirin.analysis import ForwardFrame

from bloqade.analysis.reference import KEY, Ref, Whole, ReferenceAnalysis

from .. import stmts
from .._dialect import dialect


@dialect.register(key=KEY)
class _Qubit(interp.MethodTable):
    """A method table that makes each new qubit a root."""

    @interp.impl(stmts.New)
    def new(
        self, analysis: ReferenceAnalysis, frame: ForwardFrame[Ref], stmt: stmts.New
    ) -> tuple[Ref, ...]:
        """Return a reference to the new qubit as a whole root."""
        return (Whole(stmt.result),)
