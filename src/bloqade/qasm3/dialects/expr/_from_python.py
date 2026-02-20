import ast

from kirin import ir, types, lowering

from . import stmts
from ._dialect import dialect
from bloqade.qasm3.types import BitType, BitRegType, QRegType, QubitType
from bloqade.qasm3.dialects.core import stmts as core_stmts


@dialect.register
class QASM3ExprLowering(lowering.FromPythonAST):

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
                f"unsupported QASM 3.0 constant type {type(node.value)}"
            )

    def lower_Subscript(self, state: lowering.State, node: ast.Subscript):
        value = state.lower(node.value).expect_one()
        index = state.lower(node.slice).expect_one()

        if not index.type.is_subseteq(types.Int):
            raise lowering.BuildError(
                f"unsupported subscript index type {index.type},"
                " only integer indices are supported in QASM 3.0"
            )

        if not isinstance(node.ctx, ast.Load):
            raise lowering.BuildError(
                f"unsupported subscript context {node.ctx},"
                " cannot write to subscript in QASM 3.0"
            )

        if value.type.is_subseteq(QRegType):
            stmt = core_stmts.QRegGet(reg=value, idx=index)
            stmt.result.type = QubitType
        elif value.type.is_subseteq(BitRegType):
            stmt = core_stmts.BitRegGet(reg=value, idx=index)
            stmt.result.type = BitType
        else:
            raise lowering.BuildError(
                f"unsupported subscript value type {value.type},"
                " only QReg and BitReg are supported in QASM 3.0"
            )

        return state.current_frame.push(stmt)

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
        else:
            raise lowering.BuildError(f"unsupported QASM 3.0 binop {node.op}")
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
            raise lowering.BuildError(f"unsupported QASM 3.0 unaryop {node.op}")
