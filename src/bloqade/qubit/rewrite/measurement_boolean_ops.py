from dataclasses import dataclass

from kirin.ir import Statement
from kirin.dialects import py, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.types import MeasurementResultType
from bloqade.qubit.stmts import IsOne


@dataclass
class RewriteMeasurementBooleanOps(RewriteRule):
    """rewrite rule to desugar `and` / `or` and `not` on measurement results"""

    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        """rewrite `and` / `or` and `not`"""
        if isinstance(node, py.Not):
            return self.rewrite_not(node)
        elif isinstance(node, (py.And, py.Or)):
            return self.rewrite_binary(node)

        return RewriteResult()

    def rewrite_not(self, node: py.unary.Not) -> RewriteResult:
        """rewrite `not m` as `not is_one(m)`"""
        is_measurement = (
            node.value.type != node.value.type.bottom()
            and node.value.type.is_subseteq(MeasurementResultType)
        )

        if not is_measurement:
            return RewriteResult()

        lst = ilist.New(values=(node.value,))
        is_one = IsOne(lst.result)
        idx = py.Constant(0)
        get = py.GetItem(obj=is_one.result, index=idx.result)
        not_stmt = py.Not(get.result)

        # insert
        lst.insert_before(node)
        is_one.insert_before(node)
        idx.insert_before(node)
        get.insert_before(node)
        node.replace_by(not_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_binary(self, node: py.And | py.Or) -> RewriteResult:
        """rewrite `and` and `or`"""

        lhs_is_measurement = (
            node.lhs.type != node.lhs.type.bottom()
            and node.lhs.type.is_subseteq(MeasurementResultType)
        )
        rhs_is_measurement = (
            node.rhs.type != node.rhs.type.bottom()
            and node.rhs.type.is_subseteq(MeasurementResultType)
        )

        if not lhs_is_measurement and not rhs_is_measurement:
            return RewriteResult()

        idx = py.Constant(0)
        idx.insert_before(node)
        if lhs_is_measurement:
            lhs_lst = ilist.New(values=(node.lhs,))
            lhs_is_one = IsOne(lhs_lst.result)
            lhs_get = py.GetItem(lhs_is_one.result, idx.result)
            lhs_arg = lhs_get.result

            lhs_lst.insert_before(node)
            lhs_is_one.insert_before(node)
            lhs_get.insert_before(node)
        else:
            lhs_arg = node.lhs

        if rhs_is_measurement:
            rhs_lst = ilist.New(values=(node.rhs,))
            rhs_is_one = IsOne(rhs_lst.result)
            rhs_get = py.GetItem(rhs_is_one.result, idx.result)
            rhs_arg = rhs_get.result

            rhs_lst.insert_before(node)
            rhs_is_one.insert_before(node)
            rhs_get.insert_before(node)
        else:
            rhs_arg = node.rhs

        if isinstance(node, py.And):
            new_node = py.And(lhs_arg, rhs_arg)
        else:
            new_node = py.Or(lhs_arg, rhs_arg)

        node.replace_by(new_node)

        return RewriteResult(has_done_something=True)
