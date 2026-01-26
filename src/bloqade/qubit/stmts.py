from kirin import ir, types, interp, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist
from kirin.analysis.typeinfer import TypeInference

from bloqade.types import QubitType, MeasurementResultType

from ._dialect import dialect


@statement(dialect=dialect)
class New(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    result: ir.ResultValue = info.result(QubitType)


Len = types.TypeVar("Len", bound=types.Int)


@statement(dialect=dialect)
class Measure(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, Len])
    result: ir.ResultValue = info.result(ilist.IListType[MeasurementResultType, Len])


@statement(dialect=dialect)
class QubitId(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), ir.Pure()})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, Len])
    result: ir.ResultValue = info.result(ilist.IListType[types.Int, Len])


@statement(dialect=dialect)
class MeasurementId(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), ir.Pure()})
    measurements: ir.SSAValue = info.argument(
        ilist.IListType[MeasurementResultType, Len]
    )
    result: ir.ResultValue = info.result(ilist.IListType[types.Int, Len])


@statement(dialect=dialect)
class Reset(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


@statement
class MeasurementPredicate(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), ir.Pure()})
    measurements: ir.SSAValue = info.argument(
        ilist.IListType[MeasurementResultType, Len]
    )
    result: ir.ResultValue = info.result(ilist.IListType[types.Bool, Len])


@statement(dialect=dialect)
class IsZero(MeasurementPredicate):
    pass


@statement(dialect=dialect)
class IsOne(MeasurementPredicate):
    pass


@statement(dialect=dialect)
class IsLost(MeasurementPredicate):
    pass


# TODO: investigate why this is needed to get type inference to be correct.
@dialect.register(key="typeinfer")
class __TypeInfer(interp.MethodTable):
    @interp.impl(Measure)
    def measure_list(
        self, _interp: TypeInference, frame: interp.AbstractFrame, stmt: Measure
    ):
        qubit_type = frame.get(stmt.qubits)

        if not qubit_type.is_subseteq(
            ilist.IListType[QubitType, types.Any]
        ) or qubit_type.is_subseteq(types.Bottom):
            return (types.Bottom,)

        eltype, len_type = qubit_type.vars

        if eltype.is_subseteq(QubitType) and not eltype.is_subseteq(types.Bottom):
            measurement_eltype = MeasurementResultType
        else:
            measurement_eltype = types.Bottom

        return (ilist.IListType[measurement_eltype, len_type],)
