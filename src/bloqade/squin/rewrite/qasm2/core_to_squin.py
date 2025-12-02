from kirin import ir
from kirin.dialects import py, func, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.types import MeasurementResultType
from bloqade.qasm2.dialects.core import stmts as core_stmts


class QASM2CoreToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case core_stmts.QRegNew():
                return self.rewrite_QRegNew(node)
            case core_stmts.CRegNew():
                return self.rewrite_CRegNew(node)
            case core_stmts.Reset():
                return self.rewrite_Reset(node)
            case core_stmts.QRegGet():
                return self.rewrite_Get(node)
            case _:
                return RewriteResult()

    def rewrite_QRegNew(self, stmt: core_stmts.QRegNew) -> RewriteResult:
        qalloc_invoke_stmt = func.Invoke(
            callee=squin.qubit.qalloc, inputs=(stmt.n_qubits,)
        )
        stmt.replace_by(qalloc_invoke_stmt)
        return RewriteResult(has_done_something=True)

    def rewrite_CRegNew(self, stmt: core_stmts.CRegNew) -> RewriteResult:

        measurement_list = ilist.New(values=(), elem_type=MeasurementResultType)
        stmt.replace_by(measurement_list)
        return RewriteResult(has_done_something=True)

    def rewrite_Reset(self, stmt: core_stmts.Reset) -> RewriteResult:

        squin_reset_stmt = squin.qubit.stmts.Reset(qubits=stmt.qarg)
        stmt.replace_by(squin_reset_stmt)
        return RewriteResult(has_done_something=True)

    def rewrite_Get(self, stmt: core_stmts.QRegGet) -> RewriteResult:

        get_item_stmt = py.GetItem(
            obj=stmt.reg,
            index=stmt.idx,
        )

        stmt.replace_by(get_item_stmt)
        return RewriteResult(has_done_something=True)
