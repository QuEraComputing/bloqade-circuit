import ast

from kirin import lowering

from . import stmts
from ._dialect import dialect


@dialect.register
class StimAuxLowering(lowering.FromPythonAST):

    def _const_stmt(
        self, state: lowering.State, value: int | float | str | bool
    ) -> stmts.ConstInt | stmts.ConstFloat | stmts.ConstStr | stmts.ConstBool:

        if isinstance(value, bool):
            return stmts.ConstBool(value=value)
        elif isinstance(value, int):
            return stmts.ConstInt(value=value)
        elif isinstance(value, float):
            return stmts.ConstFloat(value=value)
        elif isinstance(value, str):
            return stmts.ConstStr(value=value)
        else:
            raise lowering.BuildError(f"unsupported Stim constant type {type(value)}")

    def lower_Constant(self, state: lowering.State, node: ast.Constant):
        stmt = self._const_stmt(state, node.value)
        return state.current_frame.push(stmt)

    def lower_Expr(self, state: lowering.State, node: ast.Expr):
        return state.parent.visit(state, node.value)  # just forward the visit

    def lower_UnaryOp(self, state: lowering.State, node: ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            value = state.lower(node.operand).expect_one()
            stmt = stmts.Neg(operand=value)
            return state.current_frame.push(stmt)
        else:
            raise lowering.BuildError(f"unsupported Stim unaryop {node.op}")
