"""qubit dialect for squin language.

This dialect defines the operations that can be performed on qubits.

Depends on:
- `bloqade.squin.op`: provides the `OpType` type and semantics for operators applied to qubits.
- `kirin.dialects.ilist`: provides the `ilist.IListType` type for lists of qubits.
"""

from typing import Any, overload

from kirin import ir, types, interp, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist
from kirin.lowering import wraps

from bloqade.types import Qubit, QubitType, MeasurementResult, MeasurementResultType

dialect = ir.Dialect("squin.qubit")


@statement(dialect=dialect)
class New(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    result: ir.ResultValue = info.result(QubitType)


@statement(dialect=dialect)
class MeasureAny(ir.Statement):
    name = "measure"

    traits = frozenset({lowering.FromPythonCall()})
    input: ir.SSAValue = info.argument(types.Any)
    result: ir.ResultValue = info.result(types.Any)


@statement(dialect=dialect)
class MeasureQubit(ir.Statement):
    name = "measure.qubit"

    traits = frozenset({lowering.FromPythonCall()})
    qubit: ir.SSAValue = info.argument(QubitType)
    result: ir.ResultValue = info.result(MeasurementResultType)


Len = types.TypeVar("Len")


@statement(dialect=dialect)
class MeasureQubitList(ir.Statement):
    name = "measure.qubit.list"

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


# NOTE: no dependent types in Python, so we have to mark it Any...
@wraps(New)
def new() -> Qubit:
    """Create a new qubit.

    Returns:
        Qubit: A new qubit.
    """
    ...


@overload
def measure(input: Qubit) -> MeasurementResult: ...
@overload
def measure(
    input: ilist.IList[Qubit, Any] | list[Qubit],
) -> ilist.IList[MeasurementResult, Any]: ...


@wraps(MeasureAny)
def measure(input: Any) -> Any:
    """Measure a qubit or qubits in the list.

    Args:
        input: A qubit or a list of qubits to measure.

    Returns:
        MeasurementResult | list[MeasurementResult]: The result of the measurement. If a single qubit is measured,
            a single result is returned. If a list of qubits is measured, a list of results
            is returned.
            A MeasurementResult can represent both 0 and 1, but also atoms that are lost.
    """
    ...


@wraps(QubitId)
def get_qubit_id(qubit: Qubit) -> int: ...


@wraps(MeasurementId)
def get_measurement_id(measurement: MeasurementResult) -> int: ...


# TODO: investigate why this is needed to get type inference to be correct.
@dialect.register(key="typeinfer")
class __TypeInfer(interp.MethodTable):
    @interp.impl(MeasureQubitList)
    def measure_list(
        self, _interp, frame: interp.AbstractFrame, stmt: MeasureQubitList
    ):
        qubit_type = frame.get(stmt.qubits)

        if isinstance(qubit_type, types.Generic):
            len_type = qubit_type.vars[1]
        else:
            len_type = types.Any

        return (ilist.IListType[MeasurementResultType, len_type],)
