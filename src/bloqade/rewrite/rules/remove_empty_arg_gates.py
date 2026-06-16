from dataclasses import field, dataclass

from kirin import ir, types
from kirin.dialects import py, func, ilist
from kirin.dialects.ilist import IList
from kirin.dialects.ilist.stmts import IListType, New as IListNew
from kirin.dialects.func.stmts import Invoke, Function
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import qubit
from bloqade.types import MeasurementResultType, QubitType
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.squin.noise import stmts as noise_stmts

QuantumOperation = (
    gate_stmts.Gate,
    noise_stmts.NoiseChannel,
    qubit.stmts.Measure,
    qubit.stmts.Reset,
)
QUBIT_ARG_NAMES = frozenset(("qubits", "controls", "targets"))
BROADCAST_MODULE_PREFIXES = (
    "bloqade.squin.stdlib.broadcast.",
    "bloqade.qubit.stdlib.broadcast",
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


def is_qubit_ilist_type(typ: types.TypeAttribute) -> bool:
    if not isinstance(typ, types.Generic) or not typ.is_subseteq(IListType):
        return False

    elem_type = typ.vars[0]
    if elem_type.is_subseteq(QubitType) and not elem_type.is_subseteq(types.Bottom):
        return True

    if isinstance(elem_type, types.Generic) and elem_type.is_subseteq(IListType):
        inner_elem = elem_type.vars[0]
        return inner_elem.is_subseteq(QubitType) and not inner_elem.is_subseteq(
            types.Bottom
        )

    return False


def iter_named_qubit_args(stmt: ir.Statement) -> tuple[ir.SSAValue, ...]:
    return tuple(getattr(stmt, name) for name in QUBIT_ARG_NAMES if hasattr(stmt, name))


def iter_named_qubit_invoke_args(
    node: Invoke,
) -> tuple[ir.SSAValue, ...]:
    if not isinstance(node.callee.code, Function):
        return ()

    return tuple(
        arg
        for arg, arg_name in zip(node.inputs, node.callee.arg_names[1:])
        if arg_name in QUBIT_ARG_NAMES
    )


def all_qubit_args_empty(args: tuple[ir.SSAValue, ...]) -> bool:
    return bool(args) and all(is_empty_ilist_value(arg) for arg in args)


def is_quantum_operation_method(method: ir.Method) -> bool:
    if method.py_func is None or not method.py_func.__module__.startswith(
        BROADCAST_MODULE_PREFIXES
    ):
        return False

    operations = [
        stmt for stmt in method.code.walk() if isinstance(stmt, QuantumOperation)
    ]
    return len(operations) == 1


def is_qubit_op_wrapper(method: ir.Method) -> bool:
    for stmt in method.callable_region.walk():
        if isinstance(stmt, (Function, func.Return, *QuantumOperation)):
            continue
        if stmt.has_trait(ir.Pure):
            continue
        if isinstance(stmt, Invoke) and is_qubit_op_wrapper(stmt.callee):
            continue
        return False
    return True


def replace_empty_results(node: ir.Statement) -> bool:
    for result in node.results:
        if not result.uses:
            continue

        if isinstance(node, Invoke):
            result_type = node.callee.return_type
            if isinstance(result_type, types.TypeVar):
                result_type = ilist.IListType[result_type.vars[0], types.Literal(0)]
        elif isinstance(node, qubit.stmts.Measure):
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

        if isinstance(node, Invoke):
            result_type = node.callee.return_type
            if isinstance(result_type, types.TypeVar):
                result_type = ilist.IListType[result_type.vars[0], types.Literal(0)]
        elif isinstance(node, qubit.stmts.Measure):
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
        if isinstance(node, Invoke):
            return self._rewrite_invoke(node)

        if isinstance(node, QuantumOperation):
            return self._rewrite_quantum_operation(node)

        return RewriteResult()

    def _rewrite_quantum_operation(self, node: ir.Statement) -> RewriteResult:
        qubit_args = iter_named_qubit_args(node)
        if not all_qubit_args_empty(qubit_args):
            return RewriteResult()

        if not replace_empty_results(node):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)

    def _rewrite_invoke(self, node: Invoke) -> RewriteResult:
        if not is_quantum_operation_method(node.callee):
            return RewriteResult()

        qubit_args = iter_named_qubit_invoke_args(node)
        if not all_qubit_args_empty(qubit_args):
            return RewriteResult()

        if not replace_empty_results(node):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)


@dataclass
class RemoveEffectlessInvokes(RewriteRule):
    """Remove zero-arg invokes of wrappers that became no-ops."""

    _cache: dict[ir.Method, bool] = field(default_factory=dict, repr=False)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, Invoke):
            return RewriteResult()

        if node.inputs:
            return RewriteResult()

        if not is_qubit_op_wrapper(node.callee):
            return RewriteResult()

        if not self._is_effectless(node.callee):
            return RewriteResult()

        if any(result.uses for result in node.results):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)

    def _is_effectless(self, method: ir.Method) -> bool:
        if method in self._cache:
            return self._cache[method]

        for block in method.callable_region.blocks:
            for stmt in block.stmts:
                if isinstance(stmt, (func.Return, func.ConstantNone, py.Constant)):
                    continue
                if isinstance(stmt, Invoke):
                    if not self._is_effectless(stmt.callee):
                        self._cache[method] = False
                        return False
                    continue
                if isinstance(stmt, QuantumOperation):
                    self._cache[method] = False
                    return False

                self._cache[method] = False
                return False

        self._cache[method] = True
        return True
