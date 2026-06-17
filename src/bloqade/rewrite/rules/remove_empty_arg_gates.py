from dataclasses import dataclass

from kirin import ir, types
from kirin.dialects import py, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.ilist import IList
from kirin.dialects.ilist.stmts import New as IListNew, IListType

from bloqade import qubit
from bloqade.types import MeasurementResultType
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.squin.noise import stmts as noise_stmts

QuantumOperation = (
    gate_stmts.Gate,
    noise_stmts.NoiseChannel,
    qubit.stmts.Measure,
    qubit.stmts.Reset,
)


def get_ilist_len(value: ir.SSAValue) -> int | None:
    coll_type = value.type
    if isinstance(coll_type, types.Generic) and coll_type.is_subseteq(IListType):
        len_type = coll_type.vars[1]
        if isinstance(len_type, types.Literal) and isinstance(len_type.data, int):
            return len_type.data

    owner = value.owner
    if isinstance(owner, IListNew):
        return len(owner.values)

    if isinstance(owner, py.Constant):
        data = owner.value.unwrap()
        if isinstance(data, IList):
            return len(data.data)
        if isinstance(data, (list, tuple)):
            return len(data)

    return None


def is_empty_ilist_value(value: ir.SSAValue) -> bool:
    return get_ilist_len(value) == 0


def qubit_args(node: ir.Statement) -> tuple[ir.SSAValue, ...] | None:
    match node:
        case gate_stmts.ControlledGate(controls=controls, targets=targets):
            return (controls, targets)
        case gate_stmts.SingleQubitGate(qubits=qubits):
            return (qubits,)
        case (
            gate_stmts.RotationGate(qubits=qubits)
            | gate_stmts.U3(qubits=qubits)
            | gate_stmts.PhasedXZ(qubits=qubits)
        ):
            return (qubits,)
        case noise_stmts.TwoQubitPauliChannel(
            controls=controls, targets=targets
        ) | noise_stmts.Depolarize2(controls=controls, targets=targets):
            return (controls, targets)
        case (
            noise_stmts.Depolarize(qubits=qubits)
            | noise_stmts.SingleQubitPauliChannel(qubits=qubits)
            | noise_stmts.QubitLoss(qubits=qubits)
            | noise_stmts.CorrelatedQubitLoss(qubits=qubits)
        ):
            return (qubits,)
        case qubit.stmts.Measure(qubits=qubits) | qubit.stmts.Reset(qubits=qubits):
            return (qubits,)
        case _:
            return None


def all_qubit_args_empty(args: tuple[ir.SSAValue, ...]) -> bool:
    return bool(args) and all(is_empty_ilist_value(arg) for arg in args)


def replace_empty_results(node: ir.Statement) -> bool:
    for result in node.results:
        if not result.uses:
            continue

        if isinstance(node, qubit.stmts.Measure):
            result_type = ilist.IListType[MeasurementResultType, types.Literal(0)]
        else:
            result_type = result.type

        if not isinstance(result_type, types.Generic) or not result_type.is_subseteq(
            IListType
        ):
            return False

    for result in node.results:
        if not result.uses:
            continue

        if isinstance(node, qubit.stmts.Measure):
            result_type = ilist.IListType[MeasurementResultType, types.Literal(0)]
        else:
            result_type = result.type

        elem_type = result_type.vars[0]
        empty = ilist.New((), elem_type=elem_type)
        empty.insert_before(node)
        result.replace_by(empty.result)

    return True


@dataclass
class RemoveEmptyArgOps(RewriteRule):
    """Remove squin gates, noise channels, and measurements on empty qubit lists."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, QuantumOperation):
            return RewriteResult()

        qubit_arg_values = qubit_args(node)
        if qubit_arg_values is None or not all_qubit_args_empty(qubit_arg_values):
            return RewriteResult()

        if not replace_empty_results(node):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)
