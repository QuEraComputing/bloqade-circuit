from typing import NoReturn, Optional, cast
from dataclasses import field, dataclass

from kirin import ir, types
from kirin.dialects import py, func, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.ir.nodes.stmt import Statement

from .. import wire, qubit


@dataclass
class WireFrame:
    use_defs: dict[ir.SSAValue, ir.SSAValue] = field(default_factory=dict)
    parent: "Optional[WireFrame]" = None

    def push_frame(self):
        self_copy = WireFrame(use_defs=self.use_defs.copy(), parent=self.parent)
        self.parent = self_copy

    def pop_frame(self):
        assert self.parent is not None, "Cannot pop the root frame"
        self.use_defs = self.parent.use_defs
        self.parent = self.parent.parent


@dataclass
class Qubit2Wire(RewriteRule):
    wire_frame: WireFrame = field(default_factory=WireFrame)

    def rewrite_Region(self, node: ir.Region) -> RewriteResult:
        added = set()
        worklist = []
        for block in node.blocks:
            if block in added:
                continue

            worklist.append(block)
            added.add(block)

            for stmt in block.stmts:
                for successor in stmt.successors:
                    if successor in added:
                        continue
                    worklist.append(successor)
                    added.add(successor)

        result = RewriteResult()
        for block in worklist:
            result = self.rewrite(block).join(result)

        return result

    def rewrite_Block(self, node: ir.Block) -> RewriteResult:
        result = RewriteResult()
        for stmt in node.stmts:
            self.rewrite(stmt).join(result)

        return result

    def default_rewrite(self, node: ir.Statement) -> RewriteResult:
        # Default rewrite does nothing, just returns the node
        return RewriteResult()

    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        return getattr(
            self, f"rewrite_{node.__class__.__name__}", self.default_rewrite
        )(node)

    def rewrite_Lambda(self, node: func.Lambda) -> NoReturn:
        raise NotImplementedError("Qubit2Wire does not support Lambda nodes directly.")

    def rewrite_Function(self, node: func.Function):
        self.frame = WireFrame()
        return self.rewrite(node.body)

    def infer_len(self, qubits: ir.SSAValue):
        typ = qubits.type
        if typ.is_subseteq(ilist.IListType[qubit.QubitType, types.Any]):
            typ = cast(types.Generic, typ)
            len_var = typ.vars[1]
            if isinstance(len_var, types.Literal):
                return cast(int, len_var.data)
        return None

    def rewrite_Apply(self, node: qubit.Apply) -> RewriteResult:
        num_qubits = self.infer_len(node.qubits)

        if num_qubits is None:
            raise NotImplementedError(
                "Cannot infer the number of qubits for Apply node."
            )
