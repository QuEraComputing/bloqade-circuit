"""This dialect provides the indexing syntax in Python lowering
for QASM2 dialects. The dialect itself does not contain new statements.

Using this dialect will be conflict with Python semantics provided by
`kirin.dialects.py.binop` and `kirin.dialects.py.indexing` dialects.
"""

import ast

from kirin import ir, types, lowering

from bloqade.qasm2.types import BitType, CRegType, QRegType, QubitType
from bloqade.qasm2.dialects import core

dialect = ir.Dialect("qasm2.indexing")


@dialect.register
class QASMCoreLowering(lowering.FromPythonAST):
    def lower_Compare(self, state: lowering.State, node: ast.Compare):
        lhs = state.lower(node.left).expect_one()
        if len(node.ops) != 1:
            raise lowering.BuildError(
                "only one comparison operator and == is supported for qasm2 lowering"
            )
        rhs = state.lower(node.comparators[0]).expect_one()
        if isinstance(node.ops[0], ast.Eq):
            stmt = core.CRegEq(lhs, rhs)
        else:
            raise lowering.BuildError(
                f"unsupported comparison operator {node.ops[0]} only Eq is supported."
            )

        return state.current_frame.push(stmt)

    def lower_Subscript(self, state: lowering.State, node: ast.Subscript):
        value = state.lower(node.value).expect_one()
        index = state.lower(node.slice).expect_one()

        if not index.type.is_subseteq(types.Int):
            raise lowering.BuildError(
                f"unsupported subscript index type {index.type},"
                " only integer indices are supported in QASM 2.0"
            )

        if not isinstance(node.ctx, ast.Load):
            raise lowering.BuildError(
                f"unsupported subscript context {node.ctx},"
                " cannot write to subscript in QASM 2.0"
            )

        if value.type.is_subseteq(QRegType):
            stmt = core.QRegGet(reg=value, idx=index)
            stmt.result.type = QubitType
        elif value.type.is_subseteq(CRegType):
            stmt = core.CRegGet(reg=value, idx=index)
            stmt.result.type = BitType
        else:
            raise lowering.BuildError(
                f"unsupported subscript value type {value.type},"
                " only QReg and CReg are supported in QASM 2.0"
            )

        return state.current_frame.push(stmt)
