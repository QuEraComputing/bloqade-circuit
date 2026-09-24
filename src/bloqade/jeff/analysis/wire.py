"""This module holds the reference analysis for jeff wires and registers."""

from dataclasses import dataclass

from kirin import ir, types, interp
from kirin.analysis.forward import ForwardFrame

from bloqade.constants import constant_int
from bloqade.jeff.types import WireType, QuregType, qureg_length
from bloqade.jeff.dialects import stmts
from bloqade.analysis.reference import (
    KEY,
    CARRIED,
    UNTRACKED,
    Ref,
    Whole,
    Bottom,
    Unknown,
    Register,
    Returned,
    Positions,
    ReferenceAnalysis,
)

WIRE_KEY = "jeff.reference"
"""The registry key of the rules for jeff statements."""


@dataclass
class WireReferenceAnalysis(ReferenceAnalysis):
    """A reference analysis whose roots are jeff wires and registers.

    A gate, a reset and a measurement hand each wire on to a result, so the result
    refers to the root of the wire.
    """

    keys = (WIRE_KEY, KEY, "absint")

    def kind(self, type_: types.TypeAttribute) -> type[Whole] | type[Register] | None:
        """Return `Whole` for a wire, `Register` for a register, else None."""
        if type_.is_subseteq(QuregType):
            return Register
        if type_.is_subseteq(WireType):
            return Whole
        return None

    def register_length(self, root: ir.SSAValue, call: Returned | None) -> int | None:
        """Return the constant allocation size or the typed length of a register."""
        if isinstance(root, ir.ResultValue) and isinstance(root.stmt, stmts.RegAlloc):
            return constant_int(root.stmt.size)
        return qureg_length(root.type)


@stmts.wire.dialect.register(key=WIRE_KEY)
class _Wire(interp.MethodTable):
    """A method table that follows wires through allocation, extraction and insert."""

    @interp.impl(stmts.Alloc)
    def alloc(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.Alloc,
    ) -> tuple[Ref, ...]:
        """Return the new wire as a root."""
        return (Whole(stmt.result),)

    @interp.impl(stmts.RegAlloc)
    def reg_alloc(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.RegAlloc,
    ) -> tuple[Ref, ...]:
        """Return the new register as a root."""
        return (Register(stmt.result),)

    @interp.impl(stmts.Reset)
    def reset(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.Reset,
    ) -> tuple[Ref, ...]:
        """Hand the wire on."""
        return (frame.get(stmt.wire),)

    @interp.impl(stmts.MeasureNd)
    def measure_nd(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.MeasureNd,
    ) -> tuple[Ref, ...]:
        """Hand the wire on and make the bit `Untracked`."""
        return (frame.get(stmt.wire), UNTRACKED)

    @interp.impl(stmts.RegLength)
    def length(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.RegLength,
    ) -> tuple[Ref, ...]:
        """Hand the register on and make the length `Untracked`."""
        return (frame.get(stmt.reg), UNTRACKED)

    @interp.impl(stmts.Extract)
    def extract(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.Extract,
    ) -> tuple[Ref, ...]:
        """Hand the register on and make the wire a `Slot` of the register."""
        register = frame.get(stmt.reg)
        return (register, analysis.index(register, stmt.index))

    @interp.impl(stmts.Insert)
    def insert(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.Insert,
    ) -> tuple[Ref, ...]:
        """Hand the register on if the wire returns to the slot that it came from."""
        register, wire = frame.get(stmt.reg), frame.get(stmt.wire)
        if isinstance(register, Register) and wire == analysis.index(
            register, stmt.index
        ):
            return (register,)
        return (Unknown("a register that holds a wire from another slot"),)


@stmts.gate.dialect.register(key=WIRE_KEY)
class _Gate(interp.MethodTable):
    """A method table that hands each wire of a gate on to its result."""

    @interp.impl(stmts.Gate)
    @interp.impl(stmts.Ppr)
    def gate(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.Gate | stmts.Ppr,
    ) -> tuple[Ref, ...]:
        """Return the references of the targets and then of the controls."""
        return frame.get_values((*stmt.targets, *stmt.controls))


@stmts.scf.dialect.register(key=WIRE_KEY)
class _Scf(interp.MethodTable):
    """A method table that joins the references that jeff control flow carries."""

    @interp.impl(stmts.For)
    def for_(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.For,
    ) -> tuple[Ref, ...]:
        """Run the body until the carried references stop changing."""
        carried = frame.get_values(stmt.state)
        return analysis.run_loop(frame, stmt, stmt.body, carried)

    @interp.impl(stmts.Switch)
    def switch(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.Switch,
    ) -> tuple[Ref, ...]:
        """Join the references that the branches and the default yield."""
        inputs = frame.get_values(stmt.inputs)
        joined = tuple(Bottom() for _ in stmt.results)
        for region in stmt.regions:
            with analysis.new_frame(stmt, has_parent_access=True) as inner:
                yielded = analysis.frame_call_region(inner, stmt, region, *inputs)
            frame.entries.update(inner.entries)
            if not isinstance(yielded, tuple) or len(yielded) != len(stmt.results):
                return analysis.unknown_results(stmt, CARRIED)
            joined = tuple(a.join(b) for a, b in zip(joined, yielded, strict=True))
        return joined

    @interp.impl(stmts.While)
    def while_(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.While,
    ) -> tuple[Ref, ...]:
        """Run both regions until the carried references stop changing.

        The before region yields the condition and the outputs. The after region
        takes the outputs and yields the next inputs.
        """
        carried = frame.get_values(stmt.inputs)
        # A join moves a carried reference up, and each one can move up once.
        for _ in range(len(carried) + 1):
            with analysis.new_frame(stmt, has_parent_access=True) as before:
                yielded = analysis.frame_call_region(
                    before, stmt, stmt.before, *carried
                )
            if not isinstance(yielded, tuple) or len(yielded) != len(carried) + 1:
                return analysis.unknown_results(stmt, CARRIED)
            outputs = yielded[1:]
            with analysis.new_frame(stmt, has_parent_access=True) as after:
                again = analysis.frame_call_region(after, stmt, stmt.after, *outputs)
            if not isinstance(again, tuple) or len(again) != len(carried):
                return analysis.unknown_results(stmt, CARRIED)
            joined = tuple(c.join(n) for c, n in zip(carried, again, strict=True))
            if joined == carried:
                frame.entries.update(before.entries)
                frame.entries.update(after.entries)
                return outputs
            carried = joined
        raise AssertionError("a carried reference moved up the lattice twice")

    @interp.impl(stmts.Yield)
    def yield_(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.Yield,
    ) -> interp.YieldValue[Ref]:
        """End the region with the yielded references."""
        return interp.YieldValue(frame.get_values(stmt.values))


@stmts.call.dialect.register(key=WIRE_KEY)
class _Call(interp.MethodTable):
    """A method table that runs the callee at each call with the caller's references."""

    @interp.impl(stmts.Call)
    def call(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.Call,
    ) -> tuple[Ref, ...]:
        """Return the references of the outputs in the terms of the caller."""
        match analysis.call_result(frame, stmt):
            case Positions(refs) if len(refs) == len(stmt.results):
                return refs
            case Unknown() | Bottom() as unsettled:
                return tuple(unsettled for _ in stmt.results)
        return analysis.unknown_results(stmt, "a return that does not match the call")

    @interp.impl(stmts.Return)
    def return_(
        self,
        analysis: WireReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: stmts.Return,
    ) -> interp.ReturnValue[Ref]:
        """Return the references of the returned values as `Positions`."""
        return interp.ReturnValue(Positions(frame.get_values(stmt.values)))
