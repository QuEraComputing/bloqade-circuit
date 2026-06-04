from dataclasses import field, dataclass

from kirin import ir, types, passes
from kirin.rewrite import Walk, Chain, Fixpoint, DeadCodeElimination
from kirin.dialects import py, func, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.types import MeasurementResultType
from bloqade.squin import gate, noise
from bloqade.qubit import stmts as qubit_stmts

from .callgraph import CallGraphPass


QuantumOperation = (
    gate.stmts.Gate,
    noise.stmts.NoiseChannel,
    qubit_stmts.Measure,
)
QUBIT_ARG_NAMES = frozenset(("qubits", "controls", "targets"))
BROADCAST_MODULE_PREFIXES = (
    "bloqade.squin.stdlib.broadcast.",
    "bloqade.qubit.stdlib.broadcast",
)


def _is_empty_ilist(type_: types.TypeAttribute) -> bool:
    return (
        isinstance(type_, types.Generic)
        and type_.body == ilist.IListType.body
        and isinstance(type_.vars[1], types.Literal)
        and type_.vars[1].data == 0
    )


def _is_empty_ilist_value(value: ir.SSAValue) -> bool:
    if _is_empty_ilist(value.type):
        return True
    if isinstance(value.owner, ilist.New):
        return len(value.owner.values) == 0
    if isinstance(value.owner, py.Constant):
        data = value.owner.value.unwrap()
        return isinstance(data, (list, tuple, ilist.IList)) and len(data) == 0
    return False


def _is_ilist(type_: types.TypeAttribute) -> bool:
    return isinstance(type_, types.Generic) and type_.body == ilist.IListType.body


def _is_quantum_operation_method(method: ir.Method) -> bool:
    if method.py_func is None or not method.py_func.__module__.startswith(
        BROADCAST_MODULE_PREFIXES
    ):
        return False
    operations = [
        stmt for stmt in method.code.walk() if isinstance(stmt, QuantumOperation)
    ]
    return len(operations) == 1


def _replace_empty_results(node: ir.Statement) -> bool:
    for result in node.results:
        if not result.uses:
            continue
        result_type = result.type
        if isinstance(node, func.Invoke):
            result_type = node.callee.return_type
        elif isinstance(node, qubit_stmts.Measure):
            result_type = ilist.IListType[MeasurementResultType, types.Literal(0)]
        if not _is_ilist(result_type):
            return False

    for result in node.results:
        if not result.uses:
            continue
        result_type = (
            node.callee.return_type if isinstance(node, func.Invoke) else result.type
        )
        if isinstance(node, qubit_stmts.Measure):
            result_type = ilist.IListType[MeasurementResultType, types.Literal(0)]
        elem_type = result_type.vars[0]
        empty = ilist.New((), elem_type=elem_type)
        empty.insert_before(node)
        result.replace_by(empty.result)
    return True


@dataclass
class RemoveEmptyArgOperations(RewriteRule):
    """Remove quantum operations whose compile-time qubit lists are empty."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if isinstance(node, func.Invoke):
            return self._rewrite_invoke(node)
        if isinstance(node, QuantumOperation):
            return self._rewrite_quantum_operation(node)
        return RewriteResult()

    def _rewrite_invoke(self, node: func.Invoke) -> RewriteResult:
        if not _is_quantum_operation_method(node.callee):
            return RewriteResult()

        qubit_args = [
            arg
            for arg, arg_name in zip(node.inputs, node.callee.arg_names[1:])
            if arg_name in QUBIT_ARG_NAMES
        ]
        if not qubit_args or not all(_is_empty_ilist_value(arg) for arg in qubit_args):
            return RewriteResult()
        if not _replace_empty_results(node):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)

    def _rewrite_quantum_operation(self, node: ir.Statement) -> RewriteResult:
        qubit_args = [
            getattr(node, arg_name)
            for arg_name in QUBIT_ARG_NAMES
            if hasattr(node, arg_name)
        ]
        if not qubit_args or not all(_is_empty_ilist_value(arg) for arg in qubit_args):
            return RewriteResult()
        if not _replace_empty_results(node):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)


@dataclass
class RemoveEmptyArgGates(passes.Pass):
    """Remove gates, noise channels, and measurements on empty qubit lists.

    The pass walks the full call graph so it handles both direct quantum
    statements and the stdlib functions normally used to construct them.
    """

    callgraph_pass: CallGraphPass = field(init=False)

    def __post_init__(self):
        rule = Fixpoint(
            Walk(
                Chain(
                    RemoveEmptyArgOperations(),
                    DeadCodeElimination(),
                )
            )
        )
        self.callgraph_pass = CallGraphPass(
            dialects=self.dialects,
            no_raise=self.no_raise,
            rule=rule,
        )

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        return self.callgraph_pass.unsafe_run(mt)
