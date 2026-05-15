from kirin import ir, types, lowering
from kirin.decl import info, statement


@statement
class StimStatement(ir.Statement):
    """Base class for all stim instruction statements with tag support."""

    name = "stim_statement"
    traits = frozenset({lowering.FromPythonCall()})
    tag: str = info.attribute(types.String, default=None)
