from abc import ABC
from typing import Generic, TypeVar, overload
from dataclasses import field, dataclass

from kirin import ir, idtable, interp
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
        sym_name = method.sym_name if method.sym_name is not None else ""
        return self.call(method, ast.Name(sym_name), *args)

    def emit_block(self, frame: EmitQASM2Frame, block: ir.Block) -> ast.Node | None:
        for stmt in block.stmts:
            result = self.frame_eval(frame, stmt)
            if isinstance(result, tuple):
                if len(result) == 0:
                    continue
                keys = getattr(stmt, "_results", None) or getattr(stmt, "results", None)
                if keys is None:
                    continue
                frame.set_values(keys, result)
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

@dataclass
class SymbolTable(idtable.IdTable[ir.Statement]):
    def add(self, value: ir.Statement) -> str:
        id = self.next_id
        if (trait := value.get_trait(ir.SymbolOpInterface)) is not None:
            value_name = trait.get_sym_name(value).unwrap()
            curr_ind = self.name_count.get(value_name, 0)
            suffix = f"_{curr_ind}" if curr_ind != 0 else ""
            self.name_count[value_name] = curr_ind + 1
            name = self.prefix + value_name + suffix
            self.table[value] = name
        else:
            name = f"{self.prefix}{self.prefix_if_none}{id}"
            self.next_id += 1
            self.table[value] = name
        return name

    def __getitem__(self, value: ir.Statement) -> str:
        if value in self.table:
            return self.table[value]
        raise KeyError(f"Symbol {value} not found in SymbolTable")

    def get(self, value: ir.Statement, default: str | None = None) -> str | None:
        if value in self.table:
            return self.table[value]
        return default
