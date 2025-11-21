from copy import deepcopy

from kirin import types as kirin_types, interp
from kirin.dialects import py, scf, func, ilist
from kirin.ir.attrs.py import PyAttr

from bloqade import qubit, annotate

from .lattice import (
    AnyMeasureId,
    NotMeasureId,
    KnownMeasureId,
    MeasureIdTuple,
    ConstantCarrier,
    InvalidMeasureId,
    ImmutableMeasureIds,
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
        ## "...safely assume the type inference will give you what you need"
        qubits_type = stmt.qubits.type
        # vars[0] is just the type of the elements in the ilist,
        # vars[1] can contain a literal with length information
        num_qubits = qubits_type.vars[1]
        if not isinstance(num_qubits, kirin_types.Literal):
            return (AnyMeasureId(),)

        record_idxs = frame.global_record_state.add_record_idxs(num_qubits.data)

        return (MeasureIdTuple(data=tuple(record_idxs)),)


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
            and kirin_types.is_tuple_of(measure_id_tuple_at_stmt.data, KnownMeasureId)
        ):
            return (InvalidMeasureId(),)

        final_record_idxs = [
            deepcopy(record_idx) for record_idx in measure_id_tuple_at_stmt.data
        ]

        return (ImmutableMeasureIds(data=tuple(final_record_idxs)),)


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

        return (MeasureIdTuple(frame.get_values(stmt.values)),)


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
        self, interp: MeasurementIDAnalysis, frame: interp.Frame, stmt: py.assign.Alias
    ):

        input = frame.get(stmt.value)
        return (input,)


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
class LoopHandling(interp.MethodTable):
    @interp.impl(scf.stmts.For)
    def for_loop(
        self, interp_: MeasurementIDAnalysis, frame: MeasureIDFrame, stmt: scf.stmts.For
    ):

        init_loop_vars = frame.get_values(stmt.initializers)

        # You go through the loops twice to verify the loop invariant.
        # we need to freeze the frame entries right after exiting the loop

        first_loop_frame = MeasureIDFrame(
            stmt,
            global_record_state=frame.global_record_state,
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
            global_record_state=frame.global_record_state,
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

        if captured_first_loop_vars is None or second_loop_vars is None:
            return ()

        joined_loop_vars = []
        for first_loop_var, second_loop_var in zip(
            captured_first_loop_vars, second_loop_vars
        ):
            joined_loop_vars.append(first_loop_var.join(second_loop_var))

        return tuple(joined_loop_vars)

    @interp.impl(scf.stmts.Yield)
    def for_yield(
        self,
        interp_: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: scf.stmts.Yield,
    ):
        return interp.YieldValue(frame.get_values(stmt.values))


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
