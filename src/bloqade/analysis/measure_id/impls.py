from kirin import types as kirin_types, interp
from kirin.analysis import const
from kirin.dialects import py, scf, func, ilist

from bloqade import qubit
from bloqade.decoders.dialects import annotate
from bloqade.record_idx_helper import (
    GetRecIdxFromPredicate,
    GetRecIdxFromMeasurement,
    dialect as record_idx_helper_dialect,
)

from .lattice import (
    RecId,
    Predicate,
    DetectorId,
    AnyMeasureId,
    NotMeasureId,
    ObservableId,
    RawMeasureId,
    MeasureIdBool,
    MeasureIdTuple,
    InvalidMeasureId,
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

        measure_id_bools = []
        for _ in range(num_qubits.data):
            interp.measure_count += 1
            measure_id_bools.append(RawMeasureId(interp.measure_count))

        return (MeasureIdTuple(data=tuple(measure_id_bools), obj_type=ilist.IList),)

    @interp.impl(qubit.stmts.IsLost)
    @interp.impl(qubit.stmts.IsOne)
    @interp.impl(qubit.stmts.IsZero)
    def measurement_predicate(
        self,
        interp: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
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

        predicate_measure_ids = [
            MeasureIdBool(measure_id.idx, predicate)
            for measure_id in original_measure_id_tuple.data
        ]
        return (
            MeasureIdTuple(data=tuple(predicate_measure_ids), obj_type=ilist.IList),
        )


@annotate.dialect.register(key="measure_id")
class Annotate(interp.MethodTable):
    @interp.impl(annotate.stmts.SetObservable)
    def set_observable(
        self,
        interp_: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: annotate.stmts.SetObservable,
    ):
        frame.num_measures_at_stmt[stmt] = interp_.measure_count
        observable_value = ObservableId(
            idx=interp_.observable_count,
            data=frame.get(stmt.measurements),
        )
        interp_.observable_count += 1
        return (observable_value,)

    @interp.impl(annotate.stmts.SetDetector)
    def set_detector(
        self,
        interp_: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: annotate.stmts.SetDetector,
    ):
        frame.num_measures_at_stmt[stmt] = interp_.measure_count

        detector_value = DetectorId(
            idx=interp_.detector_count,
            data=frame.get(stmt.measurements),
        )
        interp_.detector_count += 1
        return (detector_value,)


@ilist.dialect.register(key="measure_id")
class IList(interp.MethodTable):
    @interp.impl(ilist.New)
    # Because of the way GetItem works,
    # A user could create an ilist of bools that
    # ends up being a mixture of MeasureIdBool and NotMeasureId
    def new_ilist(
        self,
        interp: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: ilist.New,
    ):

        measure_ids_in_ilist = frame.get_values(stmt.values)
        return (MeasureIdTuple(data=tuple(measure_ids_in_ilist), obj_type=ilist.IList),)


@py.tuple.dialect.register(key="measure_id")
class PyTuple(interp.MethodTable):
    @interp.impl(py.tuple.New)
    def new_tuple(
        self, interp: MeasurementIDAnalysis, frame: MeasureIDFrame, stmt: py.tuple.New
    ):
        measure_ids_in_tuple = frame.get_values(stmt.args)
        return (MeasureIdTuple(data=tuple(measure_ids_in_tuple), obj_type=tuple),)


@py.indexing.dialect.register(key="measure_id")
class PyIndexing(interp.MethodTable):
    @interp.impl(py.GetItem)
    def getitem(
        self, interp: MeasurementIDAnalysis, frame: MeasureIDFrame, stmt: py.GetItem
    ):

        idx = interp.maybe_const(stmt.index, int)
        slice_ = interp.maybe_const(stmt.index, slice)
        idx_or_slice = idx if idx is not None else slice_

        if idx_or_slice is None:
            return (InvalidMeasureId(),)

        obj = frame.get(stmt.obj)
        if isinstance(obj, MeasureIdTuple):
            if isinstance(idx_or_slice, slice):
                return (
                    MeasureIdTuple(data=obj.data[idx_or_slice], obj_type=obj.obj_type),
                )
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
        return (frame.get(stmt.value),)


@py.binop.dialect.register(key="measure_id")
class PyBinOp(interp.MethodTable):
    @interp.impl(py.Add)
    def add(self, interp: MeasurementIDAnalysis, frame: MeasureIDFrame, stmt: py.Add):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)

        if (
            isinstance(lhs, MeasureIdTuple)
            and isinstance(rhs, MeasureIdTuple)
            and lhs.obj_type is rhs.obj_type
        ):
            return (MeasureIdTuple(data=lhs.data + rhs.data, obj_type=lhs.obj_type),)
        else:
            return (InvalidMeasureId(),)


@func.dialect.register(key="measure_id")
class Func(interp.MethodTable):
    @interp.impl(func.Return)
    def return_(
        self, _: MeasurementIDAnalysis, frame: MeasureIDFrame, stmt: func.Return
    ):
        return interp.ReturnValue(frame.get(stmt.value))

    # taken from Address Analysis implementation from Xiu-zhe (Roger) Luo
    @interp.impl(
        func.Invoke
    )  # we know the callee already, func.Call would mean we don't know the callee @ compile time
    def invoke(
        self, interp_: MeasurementIDAnalysis, frame: MeasureIDFrame, stmt: func.Invoke
    ):
        _, ret = interp_.call(
            stmt.callee.code,
            interp_.method_self(stmt.callee),
            *frame.get_values(stmt.inputs),
        )
        return (ret,)


# Just let analysis propagate through
# scf, particularly IfElse
@scf.dialect.register(key="measure_id")
class Scf(scf.absint.Methods):

    @interp.impl(scf.IfElse)
    def if_else(
        self,
        interp_: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: scf.IfElse,
    ):

        frame.num_measures_at_stmt[stmt] = interp_.measure_count

        # rest of the code taken directly from scf.absint.Methods base implementation

        if isinstance(hint := stmt.cond.hints.get("const"), const.Value):
            if hint.data:
                return self._infer_if_else_cond(interp_, frame, stmt, stmt.then_body)
            else:
                return self._infer_if_else_cond(interp_, frame, stmt, stmt.else_body)
        then_results = self._infer_if_else_cond(interp_, frame, stmt, stmt.then_body)
        else_results = self._infer_if_else_cond(interp_, frame, stmt, stmt.else_body)

        match (then_results, else_results):
            case (interp.ReturnValue(then_value), interp.ReturnValue(else_value)):
                return interp.ReturnValue(then_value.join(else_value))
            case (interp.ReturnValue(then_value), _):
                return then_results
            case (_, interp.ReturnValue(else_value)):
                return else_results
            case _:
                return interp_.join_results(then_results, else_results)

    @interp.impl(scf.For)
    def for_loop(
        self,
        interp_: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: scf.For,
    ):
        hint = stmt.iterable.hints.get("const")
        if not isinstance(hint, const.Value):
            return interp_.eval_fallback(frame, stmt)

        loop_vars = frame.get_values(stmt.initializers)
        iterable = hint.data

        body_values = {}
        for value in iterable:
            with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
                loop_vars = interp_.frame_call_region(
                    body_frame, stmt, stmt.body, NotMeasureId(), *loop_vars
                )

            for ssa, val in body_frame.entries.items():
                body_values[ssa] = body_values.setdefault(ssa, val).join(val)

            if loop_vars is None:
                loop_vars = ()
            elif isinstance(loop_vars, interp.ReturnValue):
                frame.set_values(body_frame.entries.keys(), body_frame.entries.values())
                return loop_vars

        frame.set_values(body_values.keys(), body_values.values())
        return loop_vars


@record_idx_helper_dialect.register(key="measure_id")
class RecordIdxHelperAnalysis(interp.MethodTable):

    @interp.impl(GetRecIdxFromMeasurement)
    def get_rec_idx_from_measurement(
        self,
        interp_: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: GetRecIdxFromMeasurement,
    ):
        measurement_id = frame.get(stmt.measurement)
        if not isinstance(measurement_id, (RawMeasureId, MeasureIdBool)):
            return (InvalidMeasureId(),)
        computed_idx = (measurement_id.idx - 1) - interp_.measure_count
        predicate = (
            measurement_id.predicate
            if isinstance(measurement_id, MeasureIdBool)
            else None
        )
        return (RecId(idx=computed_idx, predicate=predicate),)

    @interp.impl(GetRecIdxFromPredicate)
    def get_rec_idx_from_predicate(
        self,
        interp_: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: GetRecIdxFromPredicate,
    ):
        measurement_id = frame.get(stmt.predicate_result)
        if not isinstance(measurement_id, MeasureIdBool):
            return (InvalidMeasureId(),)
        computed_idx = (measurement_id.idx - 1) - interp_.measure_count
        return (RecId(idx=computed_idx, predicate=measurement_id.predicate),)
