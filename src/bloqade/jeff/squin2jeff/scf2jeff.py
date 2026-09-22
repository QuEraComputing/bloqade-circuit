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
    frame: Frame, results: Sequence[ir.SSAValue], classical: Sequence[int], inner: Frame
) -> tuple[Value, ...]:
    """Return the squin values of a statement from the jeff `results`.

    The first results are the classical values at the positions `classical`. The
    results of the captures of `inner` follow, and a captured root takes its
    result as its current wire.
    """
    values = dict(zip(classical, results[: len(classical)], strict=True))
    for key, result in zip(inner.captured, results[len(classical) :], strict=True):
        if key in inner.wires:
            frame.wires[key] = result
    return tuple(values.get(k) for k in range(len(inner.code.results)))


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
        """Emit a jeff loop whose state carries the classical loop values, then what the body captures."""
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
        state = (
            *(frame.scalar(stmt.initializers[k]) for k in classical),
            *(frame.supply(key) for key in inner.captured),
        )
        loop = frame.push(stmts.For(*bounds, state, body))
        return _bind(frame, tuple(loop.results), classical, inner)

    @interp.impl(scf.IfElse)
    def if_else(
        self, emit: Linearize, frame: Frame, stmt: scf.IfElse
    ) -> interp.StatementResult[Value]:
        """Emit a jeff switch on the condition with the else branch as case zero.

        Both regions take the same inputs: the second starts with what the first
        captured, and the first gets what only the second captured appended.
        """
        classical = _classical(emit.refs, tuple(stmt.results))
        frames: list[Frame] = []
        outs: list[list[ir.SSAValue]] = []
        for body in (stmt.else_body, stmt.then_body):
            with emit.new_frame(stmt) as inner:
                if frames:
                    inner.extend(frames[0])
                (arg,) = body.blocks[0].args
                cond = inner.scalar(stmt.cond) if arg.uses else None
                yielded = emit.frame_call_region(inner, stmt, body, cond)
            frames.append(inner)
            outs.append(_outs(emit, inner, stmt, yielded, classical))
        frames[0].extend(frames[1])
        regions = [emit.leave(inner, out) for inner, out in zip(frames, outs)]
        inputs = tuple(frame.supply(key) for key in frames[1].captured)
        switch = stmts.Switch(frame.scalar(stmt.cond), inputs, regions[:1], regions[1])
        return _bind(frame, tuple(frame.push(switch).results), classical, frames[1])
