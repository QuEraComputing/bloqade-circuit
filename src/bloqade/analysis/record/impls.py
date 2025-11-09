from copy import deepcopy

from kirin import types as kirin_types, interp
from kirin.dialects import py, scf, ilist

from bloqade import qubit, annotate
from bloqade.annotate.stmts import SetDetector, SetObservable

from .lattice import (
    AnyRecord,
    NotRecord,
    RecordIdx,
    RecordTuple,
    InvalidRecord,
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

        record_idxs = []
        for _ in range(num_qubits.data):
            record_idx = frame.global_record_state.increment_record_idx()
            record_idxs.append(record_idx)

        return (RecordTuple(members=tuple(record_idxs)),)


@py.indexing.dialect.register(key="record")
class PyIndexing(interp.MethodTable):
    @interp.impl(py.GetItem)
    def getitem(self, interp: RecordAnalysis, frame: RecordFrame, stmt: py.GetItem):

        idx_or_slice = interp.get_const_value((int, slice), stmt.index)
        if idx_or_slice is None:
            return (InvalidRecord(),)

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
        interp: RecordAnalysis,
        frame: RecordFrame,
        stmt: py.Alias,
    ):
        value = frame.get(stmt.value)
        if isinstance(value, RecordIdx):
            frame.global_record_state.drop_record_idx(value)
        elif isinstance(value, RecordTuple):
            for member in value.members:
                frame.global_record_state.drop_record_idx(member)

        return (value,)


@scf.dialect.register(key="record")
class LoopHandling(scf.absint.Methods):
    @interp.impl(scf.stmts.For)
    def for_loop(
        self, interp_: RecordAnalysis, frame: RecordFrame, stmt: scf.stmts.For
    ):

        # this will contain the in-loop measure variable declared outside the loop
        loop_vars = frame.get_values(stmt.initializers)
        # NotRecord in the beginning just lets the sink  have some value
        loop_vars = interp_.run_ssacfg_region(frame, stmt.body, loop_vars)

        # need to update the information in the frame
        if isinstance(loop_vars, interp.ReturnValue):
            return loop_vars
        elif loop_vars is None:
            loop_vars = ()

        return loop_vars
