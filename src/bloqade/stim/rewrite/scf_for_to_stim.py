from kirin import ir
from kirin.dialects import scf, ilist
from kirin.dialects.py import Constant
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.stim.dialects import cf
from bloqade.stim.dialects.auxiliary import ConstInt


class ScfForToStim(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement):
        if not isinstance(node, scf.stmts.For):
            return RewriteResult()

        # Convert the scf.For iterable to
        # a single integer constant
        ## Detach to allow DCE to do its job later
        loop_iterable_stmt = node.iterable.owner
        assert isinstance(loop_iterable_stmt, Constant)
        assert isinstance(loop_iterable_stmt.value, ilist.IList)
        loop_range = loop_iterable_stmt.value.data
        assert isinstance(loop_range, range)
        num_times_to_repeat = len(loop_range)

        const_repeat_num = ConstInt(value=num_times_to_repeat)
        const_repeat_num.insert_before(node)

        # figured out from scf2cf, can't just
        # point the old body into the new REPEAT body
        new_block = ir.Block()
        for stmt in node.body.blocks[0].stmts:
            if isinstance(stmt, scf.stmts.Yield):
                print(stmt.values)
                continue
            stmt.detach()
            new_block.stmts.append(stmt)

        new_region = ir.Region(new_block)

        # Create the REPEAT statement
        repeat_stmt = cf.stmts.REPEAT(
            count=const_repeat_num.result,
            body=new_region,
        )
        node.replace_by(repeat_stmt)

        return RewriteResult(has_done_something=True)
