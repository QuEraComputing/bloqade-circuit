from dataclasses import dataclass

from kirin.ir import SSAValue, Statement
from kirin.dialects import py, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.types import MeasurementResultType
from bloqade.qubit.stmts import IsOne, IsLost, IsZero


@dataclass
class RewriteMeasurementBooleanOps(RewriteRule):
    """
    Desugar measurements compared to constant integer values to calls to `is_one` / `is_zero` / `is_lost`
    """

    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        """rewrite m == 1 and m != 1"""

        inverted = isinstance(node, py.cmp.NotEq)

        if not (isinstance(node, py.cmp.Eq) or inverted):
            return RewriteResult()

        lhs_type = node.lhs.type
        rhs_type = node.rhs.type

        lhs_is_measurement = lhs_type != lhs_type.bottom() and lhs_type.is_subseteq(
            MeasurementResultType
        )
        rhs_is_measurement = rhs_type != rhs_type.bottom() and rhs_type.is_subseteq(
            MeasurementResultType
        )

        if not (lhs_is_measurement ^ rhs_is_measurement):
            return RewriteResult()

        if lhs_is_measurement:
            m = node.lhs
            c = self._try_get_const_int(node.rhs)
        else:
            m = node.rhs
            c = self._try_get_const_int(node.lhs)

        if c is None:
            return RewriteResult()

        if c == 0:
            check = IsZero
        elif c == 1:
            check = IsOne
        elif c == 2:
            check = IsLost
        else:
            return RewriteResult()

        lst = ilist.New(values=(m,))
        lst.insert_before(node)
        check_stmt = check(measurements=lst.result)
        check_stmt.insert_before(node)
        idx = py.Constant(0)
        idx.insert_before(node)
        get = py.GetItem(check_stmt.result, idx.result)

        if inverted:
            get.insert_before(node)
            not_get = py.Not(get.result)
            node.replace_by(not_get)
        else:
            node.replace_by(get)
        return RewriteResult(has_done_something=True)

    def _try_get_const_int(self, node: SSAValue) -> int | None:
        if not isinstance(owner := node.owner, py.Constant):
            return

        val = owner.value.unwrap()
        if not isinstance(val, int):
            return

        return val
