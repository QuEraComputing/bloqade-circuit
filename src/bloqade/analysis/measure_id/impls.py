from copy import deepcopy

from kirin import types as kirin_types, interp
from kirin.dialects import py, scf, func, ilist
from kirin.ir.attrs.py import PyAttr

from bloqade import qubit, gemini
from bloqade.decoders.dialects import annotate

from .lattice import (
    Predicate,
    AnyMeasureId,
    NotMeasureId,
    RawMeasureId,
    MeasureIdTuple,
    ConstantCarrier,
    InvalidMeasureId,
)
from .analysis import MeasureIDFrame, MeasurementIDAnalysis


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
        if not isinstance(original_measure_id_tuple, MeasureIdTuple):
            return (InvalidMeasureId(),)

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

        return (
            MeasureIdTuple(data=original_measure_id_tuple.data, predicate=predicate),
        )


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

        final_measure_ids = [
            deepcopy(measure_id_element)
            for measure_id_element in measure_id_tuple_at_stmt.data
        ]

        return (MeasureIdTuple(data=tuple(final_measure_ids), immutable=True),)


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
            return (self.measure_id_tuple_handling(obj, idx_or_slice),)

        # just propagate down the line
        if isinstance(obj, (AnyMeasureId, NotMeasureId)):
            return (obj,)

        # literally everything else failed
        return (InvalidMeasureId(),)

    def measure_id_tuple_handling(
        self, measure_id_tuple: MeasureIdTuple, idx_or_slice: int | slice
    ) -> RawMeasureId | MeasureIdTuple:

        if isinstance(idx_or_slice, slice):
            return MeasureIdTuple(
                data=measure_id_tuple.data[idx_or_slice],
                predicate=measure_id_tuple.predicate,
            )
        elif isinstance(idx_or_slice, int):
            raw_measure_id = measure_id_tuple.data[idx_or_slice]
            # Propagate predicate from tuple to individual RawMeasureId
            if measure_id_tuple.predicate is not None:
                raw_measure_id.predicate = measure_id_tuple.predicate
            return raw_measure_id
        else:
            return InvalidMeasureId()


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
        attempted_cloned_input = frame.global_record_state.clone_measure_ids(input)
        if attempted_cloned_input is None:
            return (input,)

        return (attempted_cloned_input,)


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

        # need to unify the IfElse entries as well
        # they should stay the same type in the loop
        unified_if_else_cond_types = {}
        for ssa_val, lattice_element in first_loop_frame.type_for_scf_conds.items():
            unified_if_else_cond_element = second_loop_frame.type_for_scf_conds[
                ssa_val
            ].join(lattice_element)
            unified_if_else_cond_types[ssa_val] = unified_if_else_cond_element

        frame.entries.update(unified_frame_buffer)
        frame.type_for_scf_conds.update(unified_if_else_cond_types)
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

        # Same RecordIdx can get copied into the parent frame twice, we need to be careful
        # to only add unique RecordIdx entries
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
        # Check for constant boolean condition first
        const_cond = interp_.maybe_const(stmt.cond, bool)
        if const_cond is not None:
            # Constant condition can't have a measure ID, run only the relevant branch
            body = stmt.then_body if const_cond else stmt.else_body
            body_frame = MeasureIDFrame(
                stmt,
                global_record_state=deepcopy(frame.global_record_state),
                parent=frame,
                has_parent_access=True,
            )
            results = interp_.frame_call_region(body_frame, stmt, body, NotMeasureId())
            if body_frame.measure_count_offset > 0:
                return tuple(AnyMeasureId() for _ in stmt.results)
            # Update parent frame entries for printing
            frame.set_values(body_frame.entries.keys(), body_frame.entries.values())
            return results

        # Non-constant condition: check if it's a measurement-based condition
        cond_measure_id = frame.get(stmt.cond)
        if (
            isinstance(cond_measure_id, RawMeasureId)
            and cond_measure_id.predicate is not None
        ):
            frame.type_for_scf_conds[stmt] = deepcopy(cond_measure_id)
        else:
            frame.type_for_scf_conds[stmt] = InvalidMeasureId()

        # Run both branches
        then_frame = MeasureIDFrame(
            stmt,
            global_record_state=deepcopy(frame.global_record_state),
            parent=frame,
            has_parent_access=True,
        )
        then_results = interp_.frame_call_region(
            then_frame, stmt, stmt.then_body, cond_measure_id
        )

        else_frame = MeasureIDFrame(
            stmt,
            global_record_state=deepcopy(frame.global_record_state),
            parent=frame,
            has_parent_access=True,
        )
        else_results = interp_.frame_call_region(
            else_frame, stmt, stmt.else_body, cond_measure_id
        )

        # If measurement occurred in either branch, return top
        if then_frame.measure_count_offset > 0 or else_frame.measure_count_offset > 0:
            return tuple(AnyMeasureId() for _ in stmt.results)

        # Update parent frame entries for printing (join entries from both branches)
        frame.set_values(then_frame.entries.keys(), then_frame.entries.values())
        frame.set_values(else_frame.entries.keys(), else_frame.entries.values())

        # Handle ReturnValue cases
        if isinstance(then_results, interp.ReturnValue) and isinstance(
            else_results, interp.ReturnValue
        ):
            return interp.ReturnValue(then_results.value.join(else_results.value))
        elif isinstance(then_results, interp.ReturnValue):
            return else_results
        elif isinstance(else_results, interp.ReturnValue):
            return then_results

        # Join results (no parent frame updates needed since measurements are forbidden)
        return interp_.join_results(then_results, else_results)


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
