from copy import deepcopy

from kirin import types as kirin_types, interp
from kirin.ir import PyAttr
from kirin.dialects import py, scf, ilist

from bloqade import qubit, annotate
from bloqade.annotate.stmts import SetDetector, SetObservable

from .lattice import (
    AnyRecord,
    NotRecord,
    RecordIdx,
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

        if not (
            isinstance(record_tuple_at_stmt, RecordTuple)
            and kirin_types.is_tuple_of(record_tuple_at_stmt.members, RecordIdx)
        ):
            return (InvalidRecord(),)

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

        # increment the parent frame measure count offset.
        # Loop analysis relies on local state tracking
        # so we use this data after exiting a loop to
        # readjust the previous global measure count.
        frame.measure_count_offset += num_qubits.data

        record_idxs = frame.global_record_state.add_record_idxs(
            num_qubits.data, id=frame.frame_id
        )

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
        # input could belong to another frame and get repossessed with an
        # independent copy in this frame. Might need to set a new frame_id here
        new_input = frame.global_record_state.clone_record_idxs(
            input, id=frame.frame_id
        )
        # two variables share the same references in the global state
        return (new_input,)


@scf.dialect.register(key="record")
class LoopHandling(interp.MethodTable):

    @interp.impl(scf.stmts.For)
    def for_loop_double_pass(
        self, interp_: RecordAnalysis, frame: RecordFrame, stmt: scf.stmts.For
    ):

        init_loop_vars = frame.get_values(stmt.initializers)

        # You go through the loops twice to verify the loop invariant.
        # we need to freeze the frame entries right after exiting the loop

        local_state = deepcopy(frame.global_record_state)
        # local_state = GlobalRecordState()

        first_loop_frame = RecordFrame(
            stmt,
            frame_id=frame.frame_id + 1,
            global_record_state=local_state,
            parent=frame,
            has_parent_access=True,
        )

        first_loop_vars = interp_.frame_call_region(
            first_loop_frame, stmt, stmt.body, InvalidRecord(), *init_loop_vars
        )

        if first_loop_vars is None:
            first_loop_vars = ()
        elif isinstance(first_loop_vars, interp.ReturnValue):
            return first_loop_vars

        captured_first_loop_entries = {}
        captured_first_loop_vars = deepcopy(first_loop_vars)

        for ssa_val, lattice_element in first_loop_frame.entries.items():
            captured_first_loop_entries[ssa_val] = deepcopy(lattice_element)

        second_loop_frame = RecordFrame(
            stmt,
            frame_id=frame.frame_id + 2,
            global_record_state=local_state,
            parent=frame,
            has_parent_access=True,
        )
        second_loop_vars = interp_.frame_call_region(
            second_loop_frame, stmt, stmt.body, InvalidRecord(), *first_loop_vars
        )

        if second_loop_vars is None:
            second_loop_vars = ()
        elif isinstance(second_loop_vars, interp.ReturnValue):
            return second_loop_vars

        # take the entries in the first and second loops
        # update the parent frame

        unified_frame_buffer = {}
        for ssa_val, lattice_element in captured_first_loop_entries.items():
            verified_latticed_element = second_loop_frame.entries[ssa_val].join(
                lattice_element
            )
            unified_frame_buffer[ssa_val] = verified_latticed_element

        frame.entries.update(unified_frame_buffer)
        frame.global_record_state.offset_existing_records(
            first_loop_frame.measure_count_offset
        )

        if captured_first_loop_vars is None or second_loop_vars is None:
            return ()

        joined_loop_vars = []
        for first_loop_var, second_loop_var in zip(
            captured_first_loop_vars, second_loop_vars
        ):
            joined_loop_vars.append(first_loop_var.join(second_loop_var))

        # TrimYield is currently disabled meaning that the same RecordIdx
        # can get copied into the parent frame twice! As a result
        # we need to be careful to only add unique RecordIdx entries
        witnessed_record_idxs = set()
        for var in joined_loop_vars:
            if isinstance(var, RecordTuple):
                for member in var.members:
                    if (
                        isinstance(member, RecordIdx)
                        and member.idx not in witnessed_record_idxs
                    ):
                        witnessed_record_idxs.add(member.idx)
                        frame.global_record_state.buffer.append(member)

        return tuple(joined_loop_vars)

    @interp.impl(scf.stmts.Yield)
    def for_yield(
        self, interp_: RecordAnalysis, frame: RecordFrame, stmt: scf.stmts.Yield
    ):
        print("yield encountered, yielding values:", frame.get_values(stmt.values))
        return interp.YieldValue(frame.get_values(stmt.values))


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
