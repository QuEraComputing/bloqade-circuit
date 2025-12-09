from copy import deepcopy

from kirin import types as kirin_types, interp
from kirin.dialects import py, scf, func, ilist
from kirin.ir.attrs.py import PyAttr

from bloqade import qubit, gemini, annotate

from .lattice import (
    Predicate,
    AnyMeasureId,
    NotMeasureId,
    RawMeasureId,
    MeasureIdTuple,
    ConstantCarrier,
    InvalidMeasureId,
    PredicatedMeasureId,
)
from .analysis import MeasureIDFrame, MeasurementIDAnalysis

# from bloqade.gemini.dialects.logical import stmts as gemini_stmts, dialect as logical_dialect


@qubit.dialect.register(key="measure_id")
class SquinQubit(interp.MethodTable):

    @interp.impl(qubit.stmts.Measure)
    def measure_qubit_list(
        self,
        interp: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: qubit.stmts.Measure,
    ):

        # try to get the length of the list
        qubits_type = stmt.qubits.type
        # vars[0] is just the type of the elements in the ilist,
        # vars[1] can contain a literal with length information
        num_qubits = qubits_type.vars[1]
        if not isinstance(num_qubits, kirin_types.Literal):
            return (AnyMeasureId(),)

        # increment the parent frame measure count offset.
        # Loop analysis relies on local state tracking
        # so we use this data after exiting a loop to
        # readjust the previous global measure count.
        frame.measure_count_offset += num_qubits.data

        measure_id_tuple = frame.global_record_state.add_record_idxs(num_qubits.data)

        return (measure_id_tuple,)

    @interp.impl(qubit.stmts.IsLost)
    @interp.impl(qubit.stmts.IsOne)
    @interp.impl(qubit.stmts.IsZero)
    def measurement_predicate(
        self,
        interp: MeasurementIDAnalysis,
        frame: interp.Frame,
        stmt: qubit.stmts.IsLost | qubit.stmts.IsOne | qubit.stmts.IsZero,
    ):
        original_measure_id_tuple = frame.get(stmt.measurements)
        if not all(
            isinstance(measure_id, RawMeasureId)
            for measure_id in original_measure_id_tuple.data
        ):
            return (InvalidMeasureId(),)

        if isinstance(stmt, qubit.stmts.IsLost):
            predicate = Predicate.IS_LOST
        elif isinstance(stmt, qubit.stmts.IsOne):
            predicate = Predicate.IS_ONE
        elif isinstance(stmt, qubit.stmts.IsZero):
            predicate = Predicate.IS_ZERO
        else:
            return (InvalidMeasureId(),)

        predicate_measure_ids = [
            PredicatedMeasureId(measure_id.idx, predicate)
            for measure_id in original_measure_id_tuple.data
        ]
        return (MeasureIdTuple(data=tuple(predicate_measure_ids)),)


@gemini.logical.dialect.register(key="measure_id")
class LogicalQubit(interp.MethodTable):
    @interp.impl(gemini.logical.stmts.TerminalLogicalMeasurement)
    def terminal_measurement(
        self,
        interp: MeasurementIDAnalysis,
        frame: interp.Frame,
        stmt: gemini.logical.stmts.TerminalLogicalMeasurement,
    ):
        # try to get the length of the list
        qubits_type = stmt.qubits.type
        # vars[0] is just the type of the elements in the ilist,
        # vars[1] can contain a literal with length information
        num_qubits = qubits_type.vars[1]
        if not isinstance(num_qubits, kirin_types.Literal):
            return (AnyMeasureId(),)

        measure_id_bools = []
        for i in range(num_qubits.data):
            measure_id_bools.append(RawMeasureId(idx=-(i + 1)))

        # Immutable usually desired for stim generation
        # but we can reuse it here to indicate
        # the measurement ids should not change anymore.
        return (MeasureIdTuple(data=tuple(measure_id_bools), immutable=True),)


@annotate.dialect.register(key="measure_id")
class Annotate(interp.MethodTable):
    @interp.impl(annotate.stmts.SetObservable)
    @interp.impl(annotate.stmts.SetDetector)
    def consumes_measurements(
        self,
        interp: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: annotate.stmts.SetObservable | annotate.stmts.SetDetector,
    ):
        measure_id_tuple_at_stmt = frame.get(stmt.measurements)

        if not (
            isinstance(measure_id_tuple_at_stmt, MeasureIdTuple)
            and kirin_types.is_tuple_of(measure_id_tuple_at_stmt.data, RawMeasureId)
        ):
            return (InvalidMeasureId(),)

        final_record_idxs = [
            deepcopy(record_idx) for record_idx in measure_id_tuple_at_stmt.data
        ]

        return (MeasureIdTuple(data=tuple(final_record_idxs), immutable=True),)


@ilist.dialect.register(key="measure_id")
class IList(interp.MethodTable):
    @interp.impl(ilist.New)
    # Because of the way GetItem works,
    # A user could create an ilist of bools that
    # ends up being a mixture of MeasureIdBool and NotMeasureId
    def new_ilist(
        self,
        interp: MeasurementIDAnalysis,
        frame: interp.Frame,
        stmt: ilist.New,
    ):

        return (MeasureIdTuple(data=frame.get_values(stmt.values)),)


@py.tuple.dialect.register(key="measure_id")
class PyTuple(interp.MethodTable):
    @interp.impl(py.tuple.New)
    def new_tuple(
        self, interp: MeasurementIDAnalysis, frame: interp.Frame, stmt: py.tuple.New
    ):
        measure_ids_in_tuple = frame.get_values(stmt.args)
        return (MeasureIdTuple(data=tuple(measure_ids_in_tuple)),)


@py.indexing.dialect.register(key="measure_id")
class PyIndexing(interp.MethodTable):
    @interp.impl(py.GetItem)
    def getitem(
        self, interp: MeasurementIDAnalysis, frame: interp.Frame, stmt: py.GetItem
    ):

        possible_idx_or_slice = interp.maybe_const(stmt.index, (int, slice))
        if possible_idx_or_slice is not None:
            idx_or_slice = possible_idx_or_slice
        else:
            idx_or_slice = frame.get(stmt.index)
            if not isinstance(idx_or_slice, ConstantCarrier):
                return (InvalidMeasureId(),)
            else:
                idx_or_slice = idx_or_slice.value

        obj = frame.get(stmt.obj)
        if isinstance(obj, MeasureIdTuple):
            if isinstance(idx_or_slice, slice):
                return (MeasureIdTuple(data=obj.data[idx_or_slice]),)
            elif isinstance(idx_or_slice, int):
                return (obj.data[idx_or_slice],)
            else:
                return (InvalidMeasureId(),)
        # just propagate these down the line
        elif isinstance(obj, (AnyMeasureId, NotMeasureId)):
            return (obj,)
        else:
            return (InvalidMeasureId(),)


@py.assign.dialect.register(key="measure_id")
class PyAssign(interp.MethodTable):
    @interp.impl(py.Alias)
    def alias(
        self,
        interp: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: py.assign.Alias,
    ):

        input = frame.get(stmt.value)

        new_input = frame.global_record_state.clone_record_idxs(input)
        return (new_input,)


@py.binop.dialect.register(key="measure_id")
class PyBinOp(interp.MethodTable):
    @interp.impl(py.Add)
    def add(self, interp: MeasurementIDAnalysis, frame: interp.Frame, stmt: py.Add):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)

        if isinstance(lhs, MeasureIdTuple) and isinstance(rhs, MeasureIdTuple):
            return (MeasureIdTuple(data=lhs.data + rhs.data),)
        else:
            return (InvalidMeasureId(),)


@func.dialect.register(key="measure_id")
class Func(interp.MethodTable):
    @interp.impl(func.Return)
    def return_(self, _: MeasurementIDAnalysis, frame: interp.Frame, stmt: func.Return):
        return interp.ReturnValue(frame.get(stmt.value))

    # taken from Address Analysis implementation from Xiu-zhe (Roger) Luo
    @interp.impl(
        func.Invoke
    )  # we know the callee already, func.Call would mean we don't know the callee @ compile time
    def invoke(
        self, interp_: MeasurementIDAnalysis, frame: interp.Frame, stmt: func.Invoke
    ):
        _, ret = interp_.call(
            stmt.callee.code,
            interp_.method_self(stmt.callee),
            *frame.get_values(stmt.inputs),
        )
        return (ret,)


@scf.dialect.register(key="measure_id")
class ScfHandling(interp.MethodTable):
    @interp.impl(scf.stmts.For)
    def for_loop(
        self, interp_: MeasurementIDAnalysis, frame: MeasureIDFrame, stmt: scf.stmts.For
    ):

        init_loop_vars = frame.get_values(stmt.initializers)

        # You go through the loops twice to verify the loop invariant.
        # we need to freeze the frame entries right after exiting the loop

        local_state = deepcopy(frame.global_record_state)

        first_loop_frame = MeasureIDFrame(
            stmt,
            global_record_state=local_state,
            parent=frame,
            has_parent_access=True,
        )
        first_loop_vars = interp_.frame_call_region(
            first_loop_frame, stmt, stmt.body, InvalidMeasureId(), *init_loop_vars
        )

        if first_loop_vars is None:
            first_loop_vars = ()
        elif isinstance(first_loop_vars, interp.ReturnValue):
            return first_loop_vars

        captured_first_loop_entries = {}
        captured_first_loop_vars = deepcopy(first_loop_vars)

        for ssa_val, lattice_element in first_loop_frame.entries.items():
            captured_first_loop_entries[ssa_val] = deepcopy(lattice_element)

        second_loop_frame = MeasureIDFrame(
            stmt,
            global_record_state=local_state,
            parent=frame,
            has_parent_access=True,
        )
        second_loop_vars = interp_.frame_call_region(
            second_loop_frame, stmt, stmt.body, InvalidMeasureId(), *first_loop_vars
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
            # print(f"Joining {lattice_element} and {second_loop_frame.entries[ssa_val]} to get {verified_latticed_element}")
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
            if isinstance(var, MeasureIdTuple):
                for member in var.data:
                    if (
                        isinstance(member, RawMeasureId)
                        and member.idx not in witnessed_record_idxs
                    ):
                        witnessed_record_idxs.add(member.idx)
                        frame.global_record_state.buffer.append(member)

        return tuple(joined_loop_vars)

    @interp.impl(scf.stmts.Yield)
    def for_yield(
        self,
        interp_: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: scf.stmts.Yield,
    ):
        return interp.YieldValue(frame.get_values(stmt.values))

    @interp.impl(scf.stmts.IfElse)
    def if_else(
        self,
        interp_: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: scf.stmts.IfElse,
    ):
        cond_measure_id = frame.get(stmt.cond)
        if isinstance(cond_measure_id, PredicatedMeasureId):
            detached_cond_measure_id = PredicatedMeasureId(
                idx=deepcopy(cond_measure_id.idx), predicate=cond_measure_id.predicate
            )
            frame.type_for_scf_conds[stmt] = detached_cond_measure_id
            return

        # If you don't get a PredicatedMeasureId, don't bother
        # converting anything
        frame.type_for_scf_conds[stmt] = InvalidMeasureId()
        # nothing to return, this thing already lives on the


@py.dialect.register(key="measure_id")
class ConstantForwarding(interp.MethodTable):
    @interp.impl(py.Constant)
    def constant(
        self,
        interp_: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: py.Constant,
    ):
        # can't use interp_.maybe_const/expect_const because it assumes the data is already
        # there to begin with...
        if not isinstance(stmt.value, PyAttr):
            return (InvalidMeasureId(),)

        expected_int_or_slice = stmt.value.data

        if not isinstance(expected_int_or_slice, (int, slice)):
            return (InvalidMeasureId(),)

        return (ConstantCarrier(value=expected_int_or_slice),)
