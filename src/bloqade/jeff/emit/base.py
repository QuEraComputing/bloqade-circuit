"""This module holds the kirin emitter that builds a jeff module from jeff dialect IR."""

from typing import TypeAlias
from contextlib import contextmanager
from dataclasses import field, dataclass
from collections.abc import Iterator

from kirin import ir
from kirin.emit import EmitABC, EmitFrame
from kirin.emit.abc import EmitTable
from kirin.worklist import WorkList

from jeff import JeffOp, JeffValue, FunctionDef

EmitValue: TypeAlias = JeffValue | tuple[JeffValue, ...] | None
"""A jeff value, the values that a function returns, or None for the `self` argument."""


@dataclass
class JeffFrame(EmitFrame[JeffValue]):
    """Hold the jeff values and the operations of one function under emission."""

    scopes: list[list[JeffOp]] = field(default_factory=lambda: [[]])
    """The operation lists of the open regions, with the function body first."""

    @property
    def operations(self) -> list[JeffOp]:
        """Return the operations of the function body."""
        return self.scopes[0]

    @contextmanager
    def scope(self) -> Iterator[list[JeffOp]]:
        """Collect the operations of one jeff region under construction."""
        operations: list[JeffOp] = []
        self.scopes.append(operations)
        try:
            yield operations
        finally:
            self.scopes.pop()

    def push(self, op: JeffOp) -> JeffOp:
        """Append an operation to the innermost open region and return it."""
        self.scopes[-1].append(op)
        return op


@dataclass
class EmitJeff(EmitABC[JeffFrame, EmitValue]):
    """Build a jeff module from jeff dialect IR."""

    keys = ("emit.jeff",)
    void = None
    dialects: ir.DialectGroup

    function_defs: list[FunctionDef] = field(default_factory=list)
    """The finished jeff functions in the order of their function index."""
    function_index: dict[ir.Statement, int] = field(default_factory=dict)
    """The jeff function index of each function that the emitter has seen."""

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> JeffFrame:
        """Create the frame that the emitter uses for one function."""
        return JeffFrame(node, has_parent_access=has_parent_access)

    def reset(self) -> None:
        """Clear the state of the previous run."""
        self.callables = EmitTable(prefix="")
        self.callable_to_emit = WorkList()
        self.function_defs = []
        self.function_index = {}
