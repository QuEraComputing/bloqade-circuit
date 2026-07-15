from dataclasses import dataclass

from kirin import ir, types
from kirin.ir.ssa import BlockArgument
from kirin.analysis import CallGraph
from kirin.dialects import py, func, ilist
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


def _get_ilist_len(value: ir.SSAValue) -> int | None:
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


def _is_empty_ilist_value(
    value: ir.SSAValue,
    *,
    call_graph: CallGraph,
    callee: ir.Method,
) -> bool:
    if _get_ilist_len(value) == 0:
        return True

    if not isinstance(value, BlockArgument):
        return False

    invoke_arg_idx = value.index - 1
    if invoke_arg_idx < 0:
        return False

    callers = call_graph.edges.get(callee, set())
    if not callers:
        return False

    found_invoke = False
    for caller in callers:
        for stmt in caller.callable_region.walk():
            if not isinstance(stmt, func.Invoke) or stmt.callee is not callee:
                continue

            found_invoke = True
            if invoke_arg_idx >= len(stmt.inputs):
                return False

            if _get_ilist_len(stmt.inputs[invoke_arg_idx]) != 0:
                return False

    return found_invoke


def _qubit_args(node: ir.Statement) -> tuple[ir.SSAValue, ...] | None:
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


@dataclass
class RemoveEmptyArgOps(RewriteRule):
    """Remove squin gates, noise channels, and measurements on empty qubit lists."""

    call_graph: CallGraph
    callee: ir.Method

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Delete quantum statements whose qubit arguments are compile-time empty."""
        if not isinstance(node, QuantumOperation):
            return RewriteResult()

        qubit_arg_values = _qubit_args(node)
        if not qubit_arg_values or not all(
            _is_empty_ilist_value(arg, call_graph=self.call_graph, callee=self.callee)
            for arg in qubit_arg_values
        ):
            return RewriteResult()

        if isinstance(node, qubit.stmts.Measure):
            for result in node.results:
                if not result.uses:
                    continue
                empty = ilist.New((), elem_type=MeasurementResultType)
                empty.insert_before(node)
                result.replace_by(empty.result)

        node.delete()
        return RewriteResult(has_done_something=True)
