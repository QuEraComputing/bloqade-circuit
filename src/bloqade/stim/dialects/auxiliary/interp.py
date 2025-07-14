from kirin import interp

from . import stmts
from ._dialect import dialect


@dialect.register
class StimAuxMethods(interp.MethodTable):

    @interp.impl(stmts.ConstFloat)
    @interp.impl(stmts.ConstInt)
    @interp.impl(stmts.ConstBool)
    @interp.impl(stmts.ConstStr)
    def const(
        self,
        interpreter: interp.Interpreter,
        frame: interp.Frame,
        stmt: stmts.ConstFloat | stmts.ConstInt | stmts.ConstBool | stmts.ConstStr,
    ):
        return (stmt.value,)

    @interp.impl(stmts.Neg)
    def neg(
        self,
        interpreter: interp.Interpreter,
        frame: interp.Frame,
        stmt: stmts.Neg,
    ):
        return (-frame.get(stmt.operand),)
