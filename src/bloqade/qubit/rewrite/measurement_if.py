from dataclasses import dataclass

from kirin import types
from kirin.ir import Statement
from kirin.dialects import py, scf, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.types import MeasurementResultType
from bloqade.qubit.stmts import IsOne


@dataclass
class RewriteMeasurementIfElse(RewriteRule):
    """
    Desugar if statements on measurements, i.e. `if m: ...` to `if is_one(m): ...`
    """

    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        """rewrite `if m: ...` to `if is_one(m): ...`"""

        if not isinstance(node, scf.IfElse):
            return RewriteResult()

        m = node.cond
        m_type = m.type
        if m_type == m_type.bottom() or not m_type.is_subseteq(MeasurementResultType):
            return RewriteResult()

        lst = ilist.New(values=(m,))
        lst.insert_before(node)
        check_stmt = IsOne(measurements=lst.result)
        check_stmt.insert_before(node)
        idx = py.Constant(0)
        idx.insert_before(node)
        get = py.GetItem(check_stmt.result, idx.result)
        get.insert_before(node)
        get.result.type = types.Bool

        node.cond = get.result

        # the branches receive the condition as block argument so we need to replace those
        for region in (node.then_body, node.else_body):
            for block in region.blocks:
                if not block.args:
                    continue
                cond_arg = block.args[0]
                cond_arg.replace_by(m)
                cond_arg.type = types.Bool

        return RewriteResult(has_done_something=True)
