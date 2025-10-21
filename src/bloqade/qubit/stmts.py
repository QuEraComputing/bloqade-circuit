from kirin import ir, types, interp, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

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
    qubit: ir.SSAValue = info.argument(QubitType)
    result: ir.ResultValue = info.result(types.Int)


@statement(dialect=dialect)
class MeasurementId(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), ir.Pure()})
    measurement: ir.SSAValue = info.argument(MeasurementResultType)
    result: ir.ResultValue = info.result(types.Int)


@statement(dialect=dialect)
class Reset(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


# TODO: investigate why this is needed to get type inference to be correct.
@dialect.register(key="typeinfer")
class __TypeInfer(interp.MethodTable):
    @interp.impl(Measure)
    def measure_list(self, _interp, frame: interp.AbstractFrame, stmt: Measure):
        qubit_type = frame.get(stmt.qubits)

        if isinstance(qubit_type, types.Generic):
            len_type = qubit_type.vars[1]
        else:
            len_type = types.Any

        return (ilist.IListType[MeasurementResultType, len_type],)
