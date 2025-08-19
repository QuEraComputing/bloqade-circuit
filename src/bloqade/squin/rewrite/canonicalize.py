from typing import cast
from dataclasses import dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import Walk, abc
from kirin.dialects import cf

from .. import op, wire, analysis


class CanonicalizeWired(abc.RewriteRule):
    def rewrite_Statement(self, node: ir.Statement) -> abc.RewriteResult:

        if (
            not isinstance(node, wire.Wired)
            or len(node.qubits) != 0
            or (parent_region := node.parent_region) is None
        ):
            return abc.RewriteResult()

        parent_block = cast(ir.Block, node.parent_block)

        # the body doesn't contain any quantum operations so we can safely inline the
        # body into the parent block

        # move all statements after `node` in the current block into another block
        after_block = ir.Block()

        stmt = node.next_stmt
        while stmt is not None:
            stmt.detach()
            after_block.stmts.append(stmt)
            stmt = node.next_stmt

        # remap all results of the node to the arguments of the after_block
        for result in node.results:
            arg = after_block.args.append_from(result.type, result.name)
            result.replace_by(arg)

        parent_block_idx = parent_region._block_idx[parent_block]
        # insert goto of parent block to the body block of the node.
        parent_region.blocks.insert(parent_block_idx + 1, after_block)
        # insert all blocks of the body of the node after the parent region
        # making sure to convert any yield statements to jump statements to the after_block
        parent_block.stmts.append(
            cf.Branch(
                arguments=(),
                successor=node.body.blocks[0],
            )
        )
        for block in reversed(node.body.blocks):
            block.detach()
            if isinstance((yield_stmt := block.last_stmt), wire.Yield):
                yield_stmt.replace_by(
                    cf.Branch(yield_stmt.values, successor=after_block)
                )

            parent_region.blocks.insert(parent_block_idx + 1, block)

        node.delete()
        return abc.RewriteResult(has_done_something=True)


@dataclass
class CanonicalizeHermitian(abc.RewriteRule):
    hermitian_values: dict[ir.SSAValue, bool]

    def rewrite_Statement(self, node: ir.Statement) -> abc.RewriteResult:
        if not isinstance(node, op.stmts.Operator):
            return abc.RewriteResult()

        maybe_hermitian = node.get_trait(op.traits.MaybeHermitian)

        if maybe_hermitian is None:
            return abc.RewriteResult()

        is_hermitian = self.hermitian_values.get(node.result)
        if is_hermitian is None:
            return abc.RewriteResult()

        maybe_hermitian.set_hermitian(node, is_hermitian)
        return abc.RewriteResult(has_done_something=True)


@dataclass
class CanonicalizeUnitary(abc.RewriteRule):
    unitary_values: dict[ir.SSAValue, bool]

    def rewrite_Statement(self, node: ir.Statement) -> abc.RewriteResult:
        if not isinstance(node, op.stmts.Operator):
            return abc.RewriteResult()

        maybe_unitary = node.get_trait(op.traits.MaybeUnitary)

        if maybe_unitary is None:
            return abc.RewriteResult()

        is_unitary = self.unitary_values.get(node.result)
        if is_unitary is None:
            return abc.RewriteResult()

        maybe_unitary.set_unitary(node, is_unitary)
        return abc.RewriteResult(has_done_something=True)


class CanonicalizeUnitaryAndHermitian(Pass):
    def unsafe_run(self, mt: ir.Method) -> abc.RewriteResult:
        unitary_analysis = analysis.UnitaryAnalysis(mt.dialects)
        unitary_frame, _ = unitary_analysis.run_analysis(mt)

        if unitary_analysis.hermitian_frame is None:
            # NOTE: something went really wrong here, but we're in a rewrite so no errors
            hermitian_values = dict()
        else:
            hermitian_values = unitary_analysis.hermitian_frame.entries

        unitary_values = unitary_frame.entries

        hermitian_rewrite = CanonicalizeHermitian(hermitian_values=hermitian_values)
        unitary_rewrite = CanonicalizeUnitary(unitary_values=unitary_values)

        result = Walk(hermitian_rewrite).rewrite(mt.code)
        return Walk(unitary_rewrite).rewrite(mt.code).join(result)
