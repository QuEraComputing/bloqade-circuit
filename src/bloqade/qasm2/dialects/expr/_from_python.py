import ast

from kirin import ir, types, lowering

from . import stmts
from ._dialect import dialect


@dialect.register
class QASMUopLowering(lowering.FromPythonAST):

    def lower_Name(self, state: lowering.State, node: ast.Name):
        name = node.id
        if isinstance(node.ctx, ast.Load):
            value = state.current_frame.get(name)
            if value is None:
                raise lowering.BuildError(f"{name} is not defined")
            return value
        elif isinstance(node.ctx, ast.Store):
            raise lowering.BuildError("unhandled store operation")
        else:  # Del
            raise lowering.BuildError("unhandled del operation")

    def lower_Assign(self, state: lowering.State, node: ast.Assign):
        # NOTE: QASM only expects one value on right hand side
        rhs = state.lower(node.value).expect_one()
        current_frame = state.current_frame
        match node:
            case ast.Assign(targets=[ast.Name(lhs_name, ast.Store())], value=_):
                rhs.name = lhs_name
                current_frame.defs[lhs_name] = rhs
            case _:
                target_syntax = ", ".join(
                    ast.unparse(target) for target in node.targets
                )
                raise lowering.BuildError(f"unsupported target syntax {target_syntax}")

    def lower_Expr(self, state: lowering.State, node: ast.Expr):
        return state.parent.visit(state, node.value)

    def lower_Constant(self, state: lowering.State, node: ast.Constant):
        if isinstance(node.value, int):
            stmt = stmts.ConstInt(value=node.value)
            return state.current_frame.push(stmt)
        elif isinstance(node.value, float):
            stmt = stmts.ConstFloat(value=node.value)
            return state.current_frame.push(stmt)
        else:
            raise lowering.BuildError(
                f"unsupported QASM 2.0 constant type {type(node.value)}"
            )

    def lower_BinOp(self, state: lowering.State, node: ast.BinOp):
        lhs = state.lower(node.left).expect_one()
        rhs = state.lower(node.right).expect_one()
        if isinstance(node.op, ast.Add):
            stmt = stmts.Add(lhs, rhs)
        elif isinstance(node.op, ast.Sub):
            stmt = stmts.Sub(lhs, rhs)
        elif isinstance(node.op, ast.Mult):
            stmt = stmts.Mul(lhs, rhs)
        elif isinstance(node.op, ast.Div):
            stmt = stmts.Div(lhs, rhs)
        elif isinstance(node.op, ast.Pow):
            stmt = stmts.Pow(lhs, rhs)
        else:
            raise lowering.BuildError(f"unsupported QASM 2.0 binop {node.op}")
        stmt.result.type = self.__promote_binop_type(lhs, rhs)
        return state.current_frame.push(stmt)

    def __promote_binop_type(
        self, lhs: ir.SSAValue, rhs: ir.SSAValue
    ) -> types.TypeAttribute:
        if lhs.type.is_subseteq(types.Float) or rhs.type.is_subseteq(types.Float):
            return types.Float
        return types.Int

    def lower_UnaryOp(self, state: lowering.State, node: ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            value = state.lower(node.operand).expect_one()
            stmt = stmts.Neg(value)
            return state.current_frame.push(stmt)
        elif isinstance(node.op, ast.UAdd):
            return state.lower(node.operand).expect_one()
        else:
            raise lowering.BuildError(f"unsupported QASM 2.0 unaryop {node.op}")
