"""Base classes for the QASM3 emitter using the EmitABC pattern.

Follows the same abstract-interpretation approach as the QASM2 emitter,
using method tables for dispatch instead of long if-chains.
"""

import math
from abc import ABC
from dataclasses import field, dataclass

from kirin import ir, interp, idtable
from kirin.emit import EmitABC, EmitFrame
from kirin.worklist import WorkList
from typing_extensions import Self


@dataclass
class EmitQASM3Frame(EmitFrame[str | None]):
    """Frame for QASM3 emission.

    Collects emitted lines (strings) and tracks SSA-to-string mappings.
    """

    body: list[str] = field(default_factory=list)
    worklist: WorkList[interp.Successor] = field(default_factory=WorkList)
    block_ref: dict[ir.Block, str | None] = field(default_factory=dict)


@dataclass
class EmitQASM3Base(EmitABC[EmitQASM3Frame, str | None], ABC):
    """Base emitter for QASM3 string output via abstract interpretation."""

    void = None
    prefix: str = field(default="", kw_only=True)
    prefix_if_none: str = field(default="var_", kw_only=True)

    output: str | None = field(init=False, default=None)
    ssa_id: idtable.IdTable[ir.SSAValue] = field(init=False)

    def initialize(self) -> Self:
        super().initialize()
        self.output = None
        self.ssa_id = idtable.IdTable[ir.SSAValue](
            prefix=self.prefix,
            prefix_if_none=self.prefix_if_none,
        )
        # callables and callable_to_emit are class-level (set by EmitABC.__init_subclass__).
        # Clear them so each run starts fresh.
        self.callables.clear()
        self.callable_to_emit = WorkList()
        return self

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> EmitQASM3Frame:
        return EmitQASM3Frame(node, has_parent_access=has_parent_access)

    def emit_block(self, frame: EmitQASM3Frame, block: ir.Block) -> str | None:
        for stmt in block.stmts:
            result = self.frame_eval(frame, stmt)
            if isinstance(result, tuple):
                frame.set_values(stmt.results, result)
        return None

    def reset(self):
        pass

    def eval_fallback(self, frame: EmitQASM3Frame, node: ir.Statement):
        return tuple(None for _ in range(len(node.results)))

    @staticmethod
    def format_float(value: float) -> str:
        """Format a float for QASM3 output, using 'pi' for common values."""
        if value == math.pi:
            return "pi"
        elif value == -math.pi:
            return "-pi"
        return repr(value)
