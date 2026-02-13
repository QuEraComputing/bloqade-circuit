from kirin import ir
from kirin.dialects import scf
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.stim.dialects import cf
from bloqade.stim.dialects.auxiliary import ConstInt
from bloqade.analysis.measure_id.util import get_scf_for_repeat_count


class ScfForToStim(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement):
        if not isinstance(node, scf.stmts.For):
            return RewriteResult()

        num_times_to_repeat = get_scf_for_repeat_count(node)
        if num_times_to_repeat is None:
            return RewriteResult()

        const_repeat_num = ConstInt(value=num_times_to_repeat)
        const_repeat_num.insert_before(node)

        # figured out from scf2cf, can't just
        # point the old body into the new REPEAT body
        new_block = ir.Block()
        for stmt in node.body.blocks[0].stmts:
            if isinstance(stmt, scf.stmts.Yield):
                continue
            stmt.detach()
            new_block.stmts.append(stmt)

        new_region = ir.Region(new_block)

        # Create the REPEAT statement
        repeat_stmt = cf.stmts.Repeat(
            count=const_repeat_num.result,
            body=new_region,
        )
        node.replace_by(repeat_stmt)

        return RewriteResult(has_done_something=True)
