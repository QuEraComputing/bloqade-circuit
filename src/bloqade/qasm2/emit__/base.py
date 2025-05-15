from abc import ABC
from dataclasses import field, dataclass

from kirin import ir, emit, idtable
from kirin.worklist import WorkList

from bloqade.qasm2.parse import ast


@dataclass
class QASM2EmitFrame(emit.EmitFrame[ast.Node | None]):
    ssa: idtable.IdTable[ir.SSAValue]
    body: list[ast.Statement] = field(default_factory=list)


@dataclass
class QASM2EmitBase(emit.EmitABC[QASM2EmitFrame, ast.Node | None], ABC):
    void = None

    # options
    prefix: str = field(default="", kw_only=True)
    prefix_if_none: str = field(default="var_", kw_only=True)

    # state
    callables: emit.julia.SymbolTable = field(init=False)
    worklist: WorkList[ir.Statement] = field(init=False)

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> QASM2EmitFrame:
        return QASM2EmitFrame(
            node,
            ssa=idtable.IdTable[ir.SSAValue](
                prefix=self.prefix,
                prefix_if_none=self.prefix_if_none,
            ),
            has_parent_access=has_parent_access,
        )

    def run(self, node: ir.Method | ir.Statement):
        if isinstance(node, ir.Method):
            node = node.code

        with self.eval_context():
            self.callables.add(node)
            self.worklist.append(node)
            while self.worklist:
                callable = self.worklist.pop()
                if callable is None:
                    break
                frame, _ = self.eval(callable)
