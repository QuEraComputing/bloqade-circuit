"""This module holds the analysis that checks how functions use wires and registers."""

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis.forward import ForwardFrame

from bloqade.jeff.types import is_linear

from .base import SHARED_KEY, Check


class LinearityAnalysis(Check[EmptyLattice]):
    """An analysis that checks that each function uses each wire and register once."""

    keys = (SHARED_KEY,)
    lattice = EmptyLattice

    def leave_function(self, frame: ForwardFrame[EmptyLattice]) -> None:
        """Check the use count of every wire and register that the function defines.

        The count includes only uses by statements inside the function.
        """
        code = frame.code
        for value in frame.entries:
            if not is_linear(value.type):
                continue
            uses = sum(code.is_ancestor(use.stmt) for use in value.uses)
            if uses == 1:
                continue
            if isinstance(value, ir.ResultValue):
                node, kind = value.owner, "result"
            elif isinstance(value, ir.BlockArgument) and value.block.parent_stmt:
                node = value.block.parent_stmt
                kind = "parameter" if node is code else "region argument"
            else:
                continue
            self.error(
                node,
                f"linear {kind} '{value.name or value}' has {uses} uses. "
                "A function must consume each wire and register exactly once.",
            )
