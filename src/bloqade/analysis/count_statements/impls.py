from kirin import ir, interp
from kirin.lattice import EmptyLattice
from kirin.dialects import scf, func, ilist
from kirin.analysis.forward import ForwardFrame

from .analysis import CountStatementAnalysis


def _resolve_callable(fn: ir.SSAValue):
    mt = CountStatementAnalysis.maybe_const(fn, ir.Method)
    if mt is not None:
        return mt.code

    owner = fn.owner
    if isinstance(owner, (func.Lambda, func.Function)):
        return owner

    return None


@func.dialect.register(key="count.statements")
class __Func(interp.MethodTable):
    @interp.impl(func.Invoke)
    def invoke(
        self,
        interp_: CountStatementAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: func.Invoke,
    ):
        _, ret = interp_.call(
            stmt.callee.code,
            EmptyLattice.bottom(),
            *(EmptyLattice.bottom() for _ in stmt.inputs),
        )
        return (ret,)

    @interp.impl(func.Call)
    def call(
        self,
        interp_: CountStatementAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: func.Call,
    ):
        code = _resolve_callable(stmt.callee)
        if code is None:
            return (EmptyLattice.bottom(),)

        _, ret = interp_.call(
            code,
            EmptyLattice.bottom(),
            *(EmptyLattice.bottom() for _ in stmt.inputs),
            **{k: EmptyLattice.bottom() for k in stmt.keys},
        )
        return (ret,)


@scf.dialect.register(key="count.statements")
class __Scf(interp.MethodTable):
    @interp.impl(scf.IfElse)
    def if_else(
        self,
        interp_: CountStatementAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.IfElse,
    ):
        with interp_.new_frame(stmt, has_parent_access=True) as then_frame:
            interp_.frame_call_region(
                then_frame,
                stmt,
                stmt.then_body,
                EmptyLattice.bottom(),
            )

        with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
            interp_.frame_call_region(
                else_frame,
                stmt,
                stmt.else_body,
                EmptyLattice.bottom(),
            )

        return tuple(EmptyLattice.bottom() for _ in range(len(stmt.results)))

    @interp.impl(scf.For)
    def for_loop(
        self,
        interp_: CountStatementAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.For,
    ):
        with interp_.new_frame(stmt, has_parent_access=True) as loop_frame:
            interp_.frame_call_region(
                loop_frame,
                stmt,
                stmt.body,
                *(EmptyLattice.bottom() for _ in range(len(stmt.args))),
            )

        return tuple(EmptyLattice.bottom() for _ in range(len(stmt.results)))


@ilist.dialect.register(key="count.statements")
class __IListMethods(interp.MethodTable):
    @interp.impl(ilist.ForEach)
    @interp.impl(ilist.Map)
    def map_(
        self,
        interp_: CountStatementAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: ilist.Map | ilist.ForEach,
    ):
        code = _resolve_callable(stmt.fn)
        if code is None:
            return (EmptyLattice.bottom(),)

        interp_.call(code, EmptyLattice.bottom(), EmptyLattice.bottom())

        return ()
