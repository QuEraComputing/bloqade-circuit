"""This module holds the reference rules for kirin's own dialects."""

from kirin import interp
from kirin.dialects import py, scf, func, ilist
from kirin.analysis.forward import ForwardFrame

from bloqade.constants import constant_int

from .lattice import (
    UNTRACKED,
    Ref,
    Items,
    Members,
    Unknown,
    Register,
    Positions,
)
from .analysis import KEY, ReferenceAnalysis


@py.assign.dialect.register(key=KEY)
class _Assign(interp.MethodTable):
    """A method table that passes a reference through an alias."""

    @interp.impl(py.assign.Alias)
    def alias(
        self,
        analysis: ReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: py.assign.Alias,
    ) -> tuple[Ref, ...]:
        """Return the reference of the aliased value."""
        return (frame.get(stmt.value),)


@ilist.dialect.register(key=KEY)
class _IList(interp.MethodTable):
    """A method table that builds the references of literal lists and maps."""

    @interp.impl(ilist.New)
    def new(
        self, analysis: ReferenceAnalysis, frame: ForwardFrame[Ref], stmt: ilist.New
    ) -> tuple[Ref, ...]:
        """Return `Items` if the list holds tracked state, and `Untracked` otherwise."""
        members = frame.get_values(stmt.values)
        if analysis.kind(stmt.result.type) is not None or any(
            m != UNTRACKED for m in members
        ):
            return (Items(members),)
        return (UNTRACKED,)

    @interp.impl(ilist.Map)
    def map_(
        self, analysis: ReferenceAnalysis, frame: ForwardFrame[Ref], stmt: ilist.Map
    ) -> tuple[Ref, ...]:
        """Return the result as a register root if the map produces tracked values."""
        if analysis.kind(stmt.result.type) is Register:
            return (Register(stmt.result),)
        return (UNTRACKED,)


@py.binop.dialect.register(key=KEY)
class _BinOp(interp.MethodTable):
    """A method table that concatenates literal lists."""

    @interp.impl(py.binop.Add)
    def add(
        self, analysis: ReferenceAnalysis, frame: ForwardFrame[Ref], stmt: py.binop.Add
    ) -> tuple[Ref, ...]:
        """Join the items of two literal lists, and make other sums `Unknown`."""
        left, right = frame.get(stmt.lhs), frame.get(stmt.rhs)
        if isinstance(left, Items) and isinstance(right, Items):
            return (Items(left.refs + right.refs),)
        return analysis.unknown_results(stmt, "a concatenation of registers")


@py.tuple.dialect.register(key=KEY)
class _Tuple(interp.MethodTable):
    """A method table that builds the references of tuples."""

    @interp.impl(py.tuple.New)
    def new(
        self, analysis: ReferenceAnalysis, frame: ForwardFrame[Ref], stmt: py.tuple.New
    ) -> tuple[Ref, ...]:
        """Return the references of the tuple members as `Positions`."""
        return (Positions(frame.get_values(stmt.args)),)


@py.indexing.dialect.register(key=KEY)
class _Indexing(interp.MethodTable):
    """A method table that reads items of registers, lists and tuples."""

    @interp.impl(py.indexing.GetItem)
    def getitem(
        self,
        analysis: ReferenceAnalysis,
        frame: ForwardFrame[Ref],
        stmt: py.indexing.GetItem,
    ) -> tuple[Ref, ...]:
        """Return the reference of the item at the index."""
        obj = frame.get(stmt.obj)
        kind = analysis.kind(stmt.result.type)
        if constant_int(stmt.index) is None:
            # A register read with a slice gives a register, which has no root.
            if isinstance(obj, Register) and kind is Register:
                return (Unknown("a slice of a register"),)
            # A tuple read at a runtime index is fine if the item is untracked.
            if isinstance(obj, Positions) and kind is None:
                return (UNTRACKED,)
        # An untracked item of a list or tuple is looked up. Any other untracked
        # read, such as a classical list, needs no reference.
        if kind is None and not isinstance(obj, Members):
            return (UNTRACKED,)
        return (analysis.index(obj, stmt.index),)


@func.dialect.register(key=KEY)
class _Func(interp.MethodTable):
    """A method table that runs the callee at each call with the caller's references."""

    @interp.impl(func.Return)
    def return_(
        self, analysis: ReferenceAnalysis, frame: ForwardFrame[Ref], stmt: func.Return
    ) -> interp.ReturnValue[Ref]:
        """Return the reference of the returned value."""
        return interp.ReturnValue(frame.get(stmt.value))

    @interp.impl(func.Invoke)
    def invoke(
        self, analysis: ReferenceAnalysis, frame: ForwardFrame[Ref], stmt: func.Invoke
    ) -> tuple[Ref, ...]:
        """Return the reference of the result in the terms of the caller."""
        return (analysis.call_result(frame, stmt),)

    @interp.impl(func.Call)
    def call(
        self, analysis: ReferenceAnalysis, frame: ForwardFrame[Ref], stmt: func.Call
    ) -> tuple[Ref, ...]:
        """Give each tracked result of a dynamic call `Unknown`."""
        return analysis.unknown_results(stmt, "the result of a dynamic call")


@scf.dialect.register(key=KEY)
class _Scf(interp.MethodTable):
    """A method table that joins the references that an `scf.for` loop carries.

    A carried value keeps its reference if the body hands back the same one.
    """

    @interp.impl(scf.For)
    def for_(
        self, analysis: ReferenceAnalysis, frame: ForwardFrame[Ref], stmt: scf.For
    ) -> tuple[Ref, ...]:
        """Run the body until the carried references stop changing."""
        carried = frame.get_values(stmt.initializers)
        return analysis.run_loop(frame, stmt, stmt.body, carried)
