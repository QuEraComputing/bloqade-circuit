"""qubit dialect for squin language.

This dialect defines the operations that can be performed on qubits.

Depends on:
- `bloqade.squin.op`: provides the `OpType` type and semantics for operators applied to qubits.
- `kirin.dialects.ilist`: provides the `ilist.IListType` type for lists of qubits.
"""

from typing import Any, overload

from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist
from kirin.lowering import wraps

from bloqade.types import Qubit, QubitType
from bloqade.squin.op.types import Op, OpType

from .types import MeasurementResult, MeasurementResultType
from .lowering import ApplyAnyCallLowering

dialect = ir.Dialect("squin.qubit")


@statement(dialect=dialect)
class New(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    n_qubits: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(ilist.IListType[QubitType, types.Any])


@statement(dialect=dialect)
class Apply(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    operator: ir.SSAValue = info.argument(OpType)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType])


@statement(dialect=dialect)
class ApplyAny(ir.Statement):
    # NOTE: custom lowering to deal with vararg calls
    traits = frozenset({ApplyAnyCallLowering()})
    operator: ir.SSAValue = info.argument(OpType)
    qubits: tuple[ir.SSAValue, ...] = info.argument()


@statement(dialect=dialect)
class Broadcast(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    operator: ir.SSAValue = info.argument(OpType)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType])


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


@overload
def apply(operator: Op, qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None:
    """Apply an operator to a list of qubits.

    Note, that when considering atom loss, lost qubits will be skipped.

    Args:
        operator: The operator to apply.
        qubits: The list of qubits to apply the operator to. The size of the list
            must be inferable and match the number of qubits expected by the operator.

    Returns:
        None
    """
    ...


@overload
def apply(operator: Op, *qubits: Qubit) -> None:
    """Apply and operator to any number of qubits.

    Note, that when considering atom loss, lost qubits will be skipped.

    Args:
        operator: The operator to apply.
        *qubits: The qubits to apply the operator to. The number of qubits must
            match the size of the operator.

    Returns:
        None
    """
    ...


@wraps(ApplyAny)
def apply(operator: Op, *qubits) -> None: ...


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


@wraps(Broadcast)
def broadcast(operator: Op, qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None:
    """Broadcast and apply an operator to a list of qubits. For example, an operator
    that expects 2 qubits can be applied to a list of 2n qubits, where n is an integer > 0.

    For controlled operators, the list of qubits is interpreted as sets of (controls, targets).
    For example

    ```
    apply(CX, [q0, q1, q2, q3])
    ```

    is equivalent to

    ```
    apply(CX, [q0, q1])
    apply(CX, [q2, q3])
    ```

    Args:
        operator: The operator to broadcast and apply.
        qubits: The list of qubits to broadcast and apply the operator to. The size of the list
            must be inferable and match the number of qubits expected by the operator.

    Returns:
        None
    """
    ...
