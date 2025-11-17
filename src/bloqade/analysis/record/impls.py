from copy import deepcopy

from kirin import types as kirin_types, interp
from kirin.ir import PyAttr
from kirin.dialects import py, scf, ilist

from bloqade import qubit, annotate
from bloqade.annotate.stmts import SetDetector, SetObservable

from .lattice import (
    AnyRecord,
    NotRecord,
    RecordTuple,
    InvalidRecord,
    ConstantCarrier,
    ImmutableRecords,
)
from .analysis import RecordFrame, RecordAnalysis


@annotate.dialect.register(key="record")
class PhysicalAnnotations(interp.MethodTable):
    # Both statements inherit from the base class "ConsumesMeasurementResults"
    # both statements consume IList of MeasurementResults, so the input type should be
    # expected to be a RecordTuple
    @interp.impl(SetObservable)
    @interp.impl(SetDetector)
    def consumes_measurements(
        self, interp: RecordAnalysis, frame: RecordFrame, stmt: SetDetector
    ):
        # Get the measurement results being consumed
        record_tuple_at_stmt = frame.get(stmt.measurements)

        final_record_idxs = [
            deepcopy(record_idx) for record_idx in record_tuple_at_stmt.members
        ]

        return (ImmutableRecords(members=tuple(final_record_idxs)),)


@qubit.dialect.register(key="record")
class SquinQubit(interp.MethodTable):

    @interp.impl(qubit.stmts.Measure)
    def measure_qubit_list(
        self,
        interp: RecordAnalysis,
        frame: RecordFrame,
        stmt: qubit.stmts.Measure,
    ):

        # try to get the length of the list
        ## "...safely assume the type inference will give you what you need"
        qubits_type = stmt.qubits.type
        # vars[0] is just the type of the elements in the ilist,
        # vars[1] can contain a literal with length information
        num_qubits = qubits_type.vars[1]
        if not isinstance(num_qubits, kirin_types.Literal):
            return (AnyRecord(),)

        record_idxs = frame.global_record_state.add_record_idxs(num_qubits.data)

        return (RecordTuple(members=tuple(record_idxs)),)


@py.indexing.dialect.register(key="record")
class PyIndexing(interp.MethodTable):
    @interp.impl(py.GetItem)
    def getitem(self, interp: RecordAnalysis, frame: RecordFrame, stmt: py.GetItem):

        # maybe_const will work fine outside of any loops because
        # constprop will put the expected data into a hint.

        # if maybeconst fails, we fall back to getting the value from the frame
        # (note that even outside loops, the constant impl will happily
        # capture integer/slice constants so if THAT fails, then something
        # has truly gone wrong).
        possible_idx_or_slice = interp.maybe_const(stmt.index, (int, slice))
        if possible_idx_or_slice is not None:
            idx_or_slice = possible_idx_or_slice
        else:
            idx_or_slice = frame.get(stmt.index)
            if not isinstance(idx_or_slice, ConstantCarrier):
                return (InvalidRecord(),)
            else:
                idx_or_slice = idx_or_slice.value

        obj = frame.get(stmt.obj)
        if isinstance(obj, RecordTuple):
            if isinstance(idx_or_slice, slice):
                return (RecordTuple(members=obj.members[idx_or_slice]),)
            elif isinstance(idx_or_slice, int):
                return (obj.members[idx_or_slice],)
            else:
                return (InvalidRecord(),)
        # just propagate these down the line
        elif isinstance(obj, (AnyRecord, NotRecord)):
            return (obj,)
        else:
            return (InvalidRecord(),)


@ilist.dialect.register(key="record")
class IList(interp.MethodTable):
    @interp.impl(ilist.New)
    def new_ilist(
        self,
        interp: RecordAnalysis,
        frame: interp.Frame,
        stmt: ilist.New,
    ):
        return (RecordTuple(frame.get_values(stmt.values)),)


@py.assign.dialect.register(key="record")
class PyAlias(interp.MethodTable):
    @interp.impl(py.Alias)
    def alias(
        self,
        interp_: RecordAnalysis,
        frame: RecordFrame,
        stmt: py.Alias,
    ):
        input = frame.get(stmt.value)  # expect this to be a RecordTuple

        # two variables share the same references in the global state
        return (input,)


@scf.dialect.register(key="record")
class LoopHandling(interp.MethodTable):
    @interp.impl(scf.stmts.For)
    def for_loop(
        self, interp_: RecordAnalysis, frame: RecordFrame, stmt: scf.stmts.For
    ):

        loop_vars = frame.get_values(stmt.initializers)

        for _ in range(2):
            loop_vars = interp_.frame_call_region(
                frame, stmt, stmt.body, InvalidRecord(), *loop_vars
            )

            if loop_vars is None:
                loop_vars = ()

            elif isinstance(loop_vars, interp.ReturnValue):
                return loop_vars

        return loop_vars

    @interp.impl(scf.stmts.Yield)
    def for_yield(
        self, interp_: RecordAnalysis, frame: RecordFrame, stmt: scf.stmts.Yield
    ):
        return interp.YieldValue(frame.get_values(stmt.values))


# Only carry about carrying integers for now because
# the current issue is that
@py.dialect.register(key="record")
class ConstantForwarding(interp.MethodTable):
    @interp.impl(py.Constant)
    def constant(
        self,
        interp_: RecordAnalysis,
        frame: RecordFrame,
        stmt: py.Constant,
    ):
        # can't use interp_.maybe_const/expect_const because it assumes the data is already
        # there to begin with...
        if not isinstance(stmt.value, PyAttr):
            return (InvalidRecord(),)

        expected_int_or_slice = stmt.value.data

        if not isinstance(expected_int_or_slice, (int, slice)):
            return (InvalidRecord(),)

        return (ConstantCarrier(value=expected_int_or_slice),)


# outside_frame -> create new frame with context manager COPIED from outside frame
# the frame and the stack are separate
