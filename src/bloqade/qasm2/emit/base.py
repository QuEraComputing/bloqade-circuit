from abc import ABC
from typing import Generic, TypeVar, overload
from dataclasses import field, dataclass

from kirin import ir, interp, idtable
from kirin.emit import EmitABC, EmitFrame
from kirin.worklist import WorkList
from typing_extensions import Self

from bloqade.qasm2.parse import ast

StmtType = TypeVar("StmtType", bound=ast.Node)
EmitNode = TypeVar("EmitNode", bound=ast.Node)


@dataclass
class EmitQASM2Frame(EmitFrame[ast.Node | None], Generic[StmtType]):
    body: list[StmtType] = field(default_factory=list)
    worklist: WorkList[interp.Successor] = field(default_factory=WorkList)
    block_ref: dict[ir.Block, ast.Node | None] = field(default_factory=dict)
    _indent: int = 0


@dataclass
class EmitQASM2Base(
    EmitABC[EmitQASM2Frame[StmtType], ast.Node | None], ABC, Generic[StmtType, EmitNode]
):
    void = None
    prefix: str = field(default="", kw_only=True)
    prefix_if_none: str = field(default="var_", kw_only=True)

    output: EmitNode | None = field(init=False)
    ssa_id: idtable.IdTable[ir.SSAValue] = field(init=False)

    def initialize(self) -> Self:
        super().initialize()
        self.output: EmitNode | None = None
        self.ssa_id = idtable.IdTable[ir.SSAValue](
            prefix=self.prefix, prefix_if_none=self.prefix_if_none
        )
        return self

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> EmitQASM2Frame[StmtType]:
        return EmitQASM2Frame(node, has_parent_access=has_parent_access)

    def run_method(
        self, method: ir.Method, args: tuple[ast.Node | None, ...]
    ) -> tuple[EmitQASM2Frame[StmtType], ast.Node | None]:
        return self.call(method, *args)

    def emit_block(self, frame: EmitQASM2Frame, block: ir.Block) -> ast.Node | None:
        for stmt in block.stmts:
            result = self.frame_eval(frame, stmt)
            if isinstance(result, tuple):
                frame.set_values(stmt.results, result)
        return None

    A = TypeVar("A")
    B = TypeVar("B")

    @overload
    def assert_node(self, typ: type[A], node: ast.Node | None) -> A: ...

    @overload
    def assert_node(
        self, typ: tuple[type[A], type[B]], node: ast.Node | None
    ) -> A | B: ...

    def assert_node(
        self,
        typ: type[A] | tuple[type[A], type[B]],
        node: ast.Node | None,
    ) -> A | B:
        if not isinstance(node, typ):
            raise TypeError(f"expected {typ}, got {type(node)}")
        return node

    def reset(self):
        pass

    def eval_fallback(self, frame: EmitQASM2Frame, node: ir.Statement):
        return tuple(None for _ in range(len(node.results)))
