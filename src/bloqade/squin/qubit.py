"""qubit dialect for squin language.

This dialect defines the operations that can be performed on qubits.

Depends on:
- `bloqade.squin.op`: provides the `OpType` type and semantics for operators applied to qubits.
- `kirin.dialects.ilist`: provides the `ilist.IListType` type for lists of qubits.
"""

from typing import Any, TypeVar, overload

from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist
from kirin.lowering import wraps

from bloqade.types import Qubit, QubitType
from bloqade.squin.op.types import Op, OpType

from .types import MeasurementResult, MeasurementResultType
from .lowering import ApplyOrBroadcastCallLowering

dialect = ir.Dialect("squin.qubit")


@statement(dialect=dialect)
class New(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    n_qubits: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(ilist.IListType[QubitType, types.Any])


@statement(dialect=dialect)
class Apply(ir.Statement):
    traits = frozenset({ApplyOrBroadcastCallLowering()})
    operator: ir.SSAValue = info.argument(OpType)
    qubits: tuple[ir.SSAValue, ...] = info.argument(QubitType)


@statement(dialect=dialect)
class Broadcast(ir.Statement):
    traits = frozenset({ApplyOrBroadcastCallLowering()})
    operator: ir.SSAValue = info.argument(OpType)
    qubits: tuple[ir.SSAValue, ...] = info.argument(ilist.IListType[QubitType])


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


@statement(dialect=dialect)
class MeasureQubitList(ir.Statement):
    name = "measure.qubit.list"

    traits = frozenset({lowering.FromPythonCall()})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType])
    result: ir.ResultValue = info.result(ilist.IListType[MeasurementResultType])


# NOTE: no dependent types in Python, so we have to mark it Any...
@wraps(New)
def new(n_qubits: int) -> ilist.IList[Qubit, Any]:
    """Create a new list of qubits.

    Args:
        n_qubits(int): The number of qubits to create.

    Returns:
        (ilist.IList[Qubit, n_qubits]) A list of qubits.
    """
    ...


@wraps(Apply)
def apply(operator: Op, *qubits: Qubit) -> None:
    """Apply an operator to qubits. The number of qubits must match the operator size

    Note, that when considering atom loss, lost qubits will be skipped.

    Args:
        operator: The operator to apply.
        *qubits: The qubits to apply the operator to. The number of qubits must
            match the size of the operator.

    Returns:
        None
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
        bool | list[bool]: The result of the measurement. If a single qubit is measured,
            a single boolean is returned. If a list of qubits is measured, a list of booleans
            is returned.
    """
    ...


OpSize = TypeVar("OpSize")


@wraps(Broadcast)
def broadcast(operator: Op, *qubits: ilist.IList[Qubit, OpSize] | list[Qubit]) -> None:
    """Broadcast and apply an operator to list(s) of qubits. The number of qubit lists must
    match the size of the operator and be of equal length. The operator is then applied
    to list elements similar to what python's map does.


    ## Usage example

    ```
    from bloqade import squin

    @squin.kernel
    def main():
        targets = squin.qubit.new(4)
        controls = squin.qubit.new(4)
        h = squin.op.h()
        squin.qubit.broadcast(h, controls)  # equivalent to applying h to each control qubit
        cx = squin.op.cx()
        squin.qubit.broadcast(cx, controls, targets)  # equivalent to applying cx to control target pairs
    ```

    Args:
        operator: The operator to broadcast and apply.
        qubits: The lists of qubits to broadcast and apply the operator to. The size of the list
            must be inferable and match the number of qubits expected by the operator.

    Returns:
        None
    """
    ...
