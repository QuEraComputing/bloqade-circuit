from kirin import types as kirin_types, interp
from kirin.analysis import const
from kirin.dialects import py, scf, func, ilist

from bloqade.squin import wire, qubit

from .lattice import (
    AnyMeasureId,
    NotMeasureId,
    MeasureIdBool,
    MeasureIdTuple,
    InvalidMeasureId,
)
from .analysis import MeasureIDFrame, MeasurementIDAnalysis

## Can't do wire right now because of
## unresolved RFC on return type
# from bloqade.squin import wire


@qubit.dialect.register(key="measure_id")
class SquinQubit(interp.MethodTable):

    @interp.impl(qubit.MeasureQubit)
    def measure_qubit(
        self,
        interp: MeasurementIDAnalysis,
        frame: interp.Frame,
        stmt: qubit.MeasureQubit,
    ):
        interp.measure_count += 1
        return (MeasureIdBool(interp.measure_count),)

    @interp.impl(qubit.MeasureQubitList)
    def measure_qubit_list(
        self,
        interp: MeasurementIDAnalysis,
        frame: interp.Frame,
        stmt: qubit.MeasureQubitList,
    ):

        # try to get the length of the list
        ## "...safely assume the type inference will give you what you need"
        qubits_type = stmt.qubits.type
        # vars[0] is just the type of the elements in the ilist,
        # vars[1] can contain a literal with length information
        num_qubits = qubits_type.vars[1]
        if not isinstance(num_qubits, kirin_types.Literal):
            return (AnyMeasureId(),)

        measure_id_bools = []
        for _ in range(num_qubits.data):
            interp.measure_count += 1
            measure_id_bools.append(MeasureIdBool(interp.measure_count))

        return (MeasureIdTuple(data=tuple(measure_id_bools)),)


@wire.dialect.register(key="measure_id")
class SquinWire(interp.MethodTable):

    @interp.impl(wire.Measure)
    def measure_qubit(
        self,
        interp: MeasurementIDAnalysis,
        frame: interp.Frame,
        stmt: wire.Measure,
    ):
        interp.measure_count += 1
        return (MeasureIdBool(interp.measure_count),)


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

        measure_ids_in_ilist = frame.get_values(stmt.values)
        return (MeasureIdTuple(data=tuple(measure_ids_in_ilist)),)


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

        idx_or_slice = interp.get_const_value((int, slice), stmt.index)
        if idx_or_slice is None:
            return (InvalidMeasureId(),)

        # hint = stmt.index.hints.get("const")
        # if hint is None or not isinstance(hint, const.Value):
        #    return (InvalidMeasureId(),)

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
        return (frame.get(stmt.value),)


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
        _, ret = interp_.run_method(
            stmt.callee,
            interp_.permute_values(
                stmt.callee.arg_names, frame.get_values(stmt.inputs), stmt.kwargs
            ),
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
