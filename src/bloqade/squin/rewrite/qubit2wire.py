from typing import NoReturn, Optional
from itertools import chain
from dataclasses import field, dataclass

from kirin import ir, types
from kirin.dialects import scf, func, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.ir.nodes.stmt import Statement

from .. import wire, qubit


class LiftIfElse(RewriteRule):
    @staticmethod
    def lifted_stmts(block: ir.Block):
        local_ssa = set()
        if (last_stmt := block.last_stmt) is not None:
            local_ssa.update(last_stmt.args)

        for stmt in block.stmts:
            if not stmt.has_trait(ir.Pure) or not local_ssa.issuperset(stmt.args):
                local_ssa.update(stmt.results)
            yield stmt

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, scf.IfElse):
            return RewriteResult()

        lifted_stmts = list(
            chain(
                self.lifted_stmts(node.then_body.blocks[0]),
                self.lifted_stmts(node.else_body.blocks[0]),
            )
        )

        for stmt in lifted_stmts:
            stmt.detach()
            stmt.insert_before(node)

        return RewriteResult(has_done_something=bool(lifted_stmts))


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

    def wrap_qubit(self, node: ir.Statement, qubit_ssa: ir.SSAValue):
        if qubit_ssa not in self.wire_frame.use_defs:
            return RewriteResult()

        wire_ssa = self.wire_frame.use_defs.pop(qubit_ssa)
        wire.Wrap(wire_ssa, qubit_ssa).insert_before(node)

        return RewriteResult(has_done_something=True)

    def default_rewrite(self, node: ir.Statement) -> RewriteResult:
        result = RewriteResult()
        for arg in node.args:
            if arg.type.is_subseteq(qubit.QubitType):
                result = self.wrap_qubit(node, arg).join(result)

            elif arg.type.is_subseteq(
                ilist.IListType[qubit.QubitType, types.Any]
            ) and isinstance(owner := arg.owner, ilist.New):
                for qubit_ssa in owner.values:
                    result = self.wrap_qubit(node, qubit_ssa).join(result)

        return result

    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        return getattr(
            self, f"rewrite_{node.__class__.__name__}", self.default_rewrite
        )(node)

    def rewrite_Lambda(self, node: func.Lambda) -> NoReturn:
        raise NotImplementedError("Qubit2Wire does not support Lambda nodes directly.")

    def rewrite_Function(self, node: func.Function):
        self.frame = WireFrame()
        return self.rewrite(node.body)

    def rewrite_Apply(self, node: qubit.Apply) -> RewriteResult:
        if not isinstance(qubits_stmt := node.qubits.owner, ilist.New):
            raise NotImplementedError("input qubits must be owned by an ilist.New")

        wires = []
        for qubit_ssa in qubits_stmt.values:
            wire_ssa = self.wire_frame.use_defs.get(qubit_ssa)
            if wire_ssa is None:
                (wire_stmt := wire.Unwrap(qubit_ssa)).insert_before(node)
                wire_ssa = wire_stmt.result

            wires.append(wire_ssa)

        (new_node := wire.Apply(node.operator, *wires)).insert_before(node)

        for new_wire_ssa, qubit_ssa in zip(new_node.results, qubits_stmt.values):
            self.wire_frame.use_defs[qubit_ssa] = new_wire_ssa

        return RewriteResult(has_done_something=True)

    def rewrite_IfElse(self, node: scf.IfElse) -> RewriteResult:
        result = RewriteResult()
        self.wire_frame.push_frame()
        then_block = node.then_body.blocks[0]
        for stmt in then_block.stmts:

            self.rewrite(stmt).join(result)

        self.wire_frame.pop_frame()

        self.wire_frame.push_frame()
        result = self.rewrite(node.else_body).join(result)
        self.wire_frame.pop_frame()

        return result
