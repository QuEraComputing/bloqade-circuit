"""This module holds the rules that emit jeff loops and switches for kirin control flow."""

from collections.abc import Mapping, Sequence

from kirin import ir, types, interp
from kirin.dialects import scf
from kirin.dialects.ilist import stmts as ilist_stmts

from bloqade.jeff.forms import loop_range
from bloqade.jeff.dialects import stmts
from bloqade.analysis.reference import Ref, Untracked

from .linearize import KEY, Frame, Value, Linearize


def _classical(
    refs: Mapping[ir.SSAValue, Ref], values: Sequence[ir.SSAValue]
) -> list[int]:
    """Return the positions of the classical values in `values`."""
    return [k for k, v in enumerate(values) if isinstance(refs[v], Untracked)]


def _outs(
    emit: Linearize,
    inner: Frame,
    stmt: ir.Statement,
    yielded: object,
    classical: Sequence[int],
) -> list[ir.SSAValue]:
    """Return the jeff values that a region of `stmt` yields at the positions `classical`.

    Each value is fitted to the type of the result of `stmt` at its position.
    """
    if not isinstance(yielded, tuple):
        raise interp.InterpreterError(f"a region of {stmt.name} does not yield")
    outs: list[ir.SSAValue] = []
    for k in classical:
        if not isinstance(yielded[k], ir.SSAValue):
            raise interp.InterpreterError(f"a region of {stmt.name} yields a list")
        outs.append(emit.fitted(inner, yielded[k], stmt.results[k].type))
    return outs


def _bind(
    classical: Sequence[int], results: Sequence[ir.SSAValue], count: int
) -> tuple[Value, ...]:
    """Return the `count` squin values of a statement from its jeff `results`.

    The results are the classical values at the positions `classical`. A qubit
    position has no jeff value, since its root names it.
    """
    values = dict(zip(classical, results, strict=True))
    return tuple(values.get(k) for k in range(count))


@scf.dialect.register(key=KEY)
class _Scf(interp.MethodTable):
    """A method table that emits jeff loops and switches for kirin control flow."""

    @interp.impl(scf.Yield)
    def yield_(
        self, emit: Linearize, frame: Frame, stmt: scf.Yield
    ) -> interp.YieldValue[Value]:
        """End a region with the values that it yields."""
        return interp.YieldValue(frame.values(stmt.values))

    @interp.impl(scf.For)
    def for_(
        self, emit: Linearize, frame: Frame, stmt: scf.For
    ) -> interp.StatementResult[Value]:
        """Emit a jeff loop whose state carries the classical loop values."""
        classical = _classical(emit.refs, stmt.initializers)
        with emit.new_frame(stmt) as inner:
            index = inner.body.args.append_from(types.Int, "index")
            carried = {
                k: inner.body.args.append_from(frame.scalar(stmt.initializers[k]).type)
                for k in classical
            }
            args = [index, *(carried.get(k) for k in range(len(stmt.initializers)))]
            yielded = emit.frame_call_region(inner, stmt, stmt.body, *args)
            body = emit.leave(inner, _outs(emit, inner, stmt, yielded, classical))
        bounds: tuple[ir.SSAValue, ir.SSAValue, ir.SSAValue]
        match loop_range(stmt.iterable):
            case ilist_stmts.Range(start=start, stop=stop, step=step):
                bounds = (frame.scalar(start), frame.scalar(stop), frame.scalar(step))
            case range(start=start, stop=stop, step=step):
                bounds = (
                    frame.push(stmts.ConstInt(value=start)).result,
                    frame.push(stmts.ConstInt(value=stop)).result,
                    frame.push(stmts.ConstInt(value=step)).result,
                )
            case _:
                raise interp.InterpreterError(f"{stmt.iterable} is not a range")
        state = tuple(frame.scalar(stmt.initializers[k]) for k in classical)
        loop = frame.push(stmts.For(*bounds, state, body))
        return _bind(classical, tuple(loop.results), len(stmt.results))

    @interp.impl(scf.IfElse)
    def if_else(
        self, emit: Linearize, frame: Frame, stmt: scf.IfElse
    ) -> interp.StatementResult[Value]:
        """Emit a jeff switch on the condition with the else branch as case zero."""
        classical = _classical(emit.refs, tuple(stmt.results))
        regions: list[ir.Region] = []
        for body in (stmt.else_body, stmt.then_body):
            with emit.new_frame(stmt) as inner:
                (arg,) = body.blocks[0].args
                cond = inner.scalar(stmt.cond) if arg.uses else None
                yielded = emit.frame_call_region(inner, stmt, body, cond)
                outs = _outs(emit, inner, stmt, yielded, classical)
                regions.append(emit.leave(inner, outs))
        switch = stmts.Switch(frame.scalar(stmt.cond), (), regions[:1], regions[1])
        return _bind(classical, tuple(frame.push(switch).results), len(stmt.results))
