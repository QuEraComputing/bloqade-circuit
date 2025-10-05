"""qubit dialect for squin language.

This dialect defines the operations that can be performed on qubits.

Depends on:
- `bloqade.squin.op`: provides the `OpType` type and semantics for operators applied to qubits.
- `kirin.dialects.ilist`: provides the `ilist.IListType` type for lists of qubits.
"""

from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import QubitType, MeasurementResultType
from bloqade.squin.op.types import OpType
from bloqade.squin.op.traits import FixedSites

from ._dialect import dialect
from .lowering import ApplyAnyCallLowering, BroadcastCallLowering


@statement(dialect=dialect)
class New(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    n_qubits: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(ilist.IListType[QubitType, types.Any])


@statement(dialect=dialect)
class Apply(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    operator: ir.SSAValue = info.argument(OpType)
    qubits: tuple[ir.SSAValue, ...] = info.argument(QubitType)


@statement(dialect=dialect)
class ApplyAny(ir.Statement):
    # NOTE: custom lowering to deal with vararg calls
    traits = frozenset({ApplyAnyCallLowering()})
    operator: ir.SSAValue = info.argument(OpType)
    qubits: tuple[ir.SSAValue, ...] = info.argument()


@statement(dialect=dialect)
class Broadcast(ir.Statement):
    traits = frozenset({BroadcastCallLowering()})
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
    """
    Reset operator for qubits and wires.
    """

    traits = frozenset({lowering.FromPythonCall(), FixedSites(1)})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


@statement(dialect=dialect)
class ResetToOne(ir.Statement):
    """
    Reset qubits to the one state. Mainly needed to accommodate cirq's GeneralizedAmplitudeDampingChannel
    """

    traits = frozenset({lowering.FromPythonCall(), FixedSites(1)})
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])
