"""This module holds the emission of the `jeff.scf` statements."""

from kirin import ir, interp

from jeff import ForSCF, JeffOp, WhileSCF, JeffValue, SwitchSCF, JeffRegion
from bloqade.jeff.dialects import stmts

from .base import EmitJeff, JeffFrame


def _region(
    emit: EmitJeff,
    stmt: ir.Statement,
    region: ir.Region,
    sources: list[JeffValue],
) -> tuple[JeffRegion, tuple[JeffValue, ...]]:
    """Emit a region of `stmt` as a jeff region and return it with its yield values."""
    # A jeff region reads no outer value, so its frame has no parent access.
    with emit.new_frame(stmt) as inner:
        yields = emit.frame_call_region(inner, stmt, region, *sources)
    if not isinstance(yields, tuple):
        raise interp.exceptions.InterpreterError(
            f"A region of {stmt.name} does not end in a yield."
        )
    region_def = JeffRegion(
        sources=sources, targets=list(yields), operations=inner.operations
    )
    return region_def, yields


@stmts.scf.dialect.register(key="emit.jeff")
class _Scf(interp.MethodTable):
    """Emit the `jeff.scf` statements."""

    @interp.impl(stmts.Yield)
    def yield_(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Yield
    ) -> interp.YieldValue[JeffValue]:
        """End a region with the values that it yields."""
        return interp.YieldValue(frame.get_values(stmt.values))

    @interp.impl(stmts.For)
    def for_(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.For
    ) -> tuple[JeffValue, ...]:
        """Emit a for loop."""
        start = frame.get(stmt.start)
        stop = frame.get(stmt.stop)
        step = frame.get(stmt.step)
        state = [frame.get(value) for value in stmt.state]

        sources = [JeffValue(start.type)] + [JeffValue(v.type) for v in state]
        region, yields = _region(emit, stmt, stmt.body, sources)
        outputs = [JeffValue(value.type) for value in yields]
        frame.push(
            JeffOp(
                "scf",
                "for",
                [start, stop, step, *state],
                outputs,
                instruction_data=ForSCF(region),
            )
        )
        return tuple(outputs)

    @interp.impl(stmts.Switch)
    def switch(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Switch
    ) -> tuple[JeffValue, ...]:
        """Emit a switch."""
        selector = frame.get(stmt.selector)
        inputs = [frame.get(value) for value in stmt.inputs]

        branch_regions: list[JeffRegion] = []
        for branch in stmt.branches:
            sources = [JeffValue(value.type) for value in inputs]
            region, _ = _region(emit, stmt, branch, sources)
            branch_regions.append(region)
        sources = [JeffValue(value.type) for value in inputs]
        default_region, default_yields = _region(emit, stmt, stmt.default, sources)

        outputs = [JeffValue(value.type) for value in default_yields]
        frame.push(
            JeffOp(
                "scf",
                "switch",
                [selector, *inputs],
                outputs,
                instruction_data=SwitchSCF(
                    branches=branch_regions, default=default_region
                ),
            )
        )
        return tuple(outputs)

    @interp.impl(stmts.While)
    def while_(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.While
    ) -> tuple[JeffValue, ...]:
        """Emit a while loop."""
        inputs = [frame.get(value) for value in stmt.inputs]

        sources = [JeffValue(value.type) for value in inputs]
        before_region, before_yields = _region(emit, stmt, stmt.before, sources)
        outputs = before_yields[1:]
        sources = [JeffValue(value.type) for value in outputs]
        after_region, _ = _region(emit, stmt, stmt.after, sources)

        results = [JeffValue(value.type) for value in outputs]
        frame.push(
            JeffOp(
                "scf",
                "while",
                inputs,
                results,
                instruction_data=WhileSCF(before_region, after_region),
            )
        )
        return tuple(results)
