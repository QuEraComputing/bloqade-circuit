from dataclasses import field, dataclass

from kirin import ir, types, passes, rewrite
from kirin.dialects import func, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.rewrite.dce import DeadCodeElimination

from bloqade import qubit
from bloqade.types import MeasurementResultType
from bloqade.squin import gate, noise

from .callgraph import CallGraphPass


def _is_empty_ilist(value: ir.SSAValue) -> bool:
    value_type = value.type
    return (
        value_type.is_subseteq(ilist.IListType)
        and len(value_type.vars) >= 2
        and isinstance(value_type.vars[1], types.Literal)
        and value_type.vars[1].data == 0
    )


def _qubit_arguments(stmt: ir.Statement) -> tuple[ir.SSAValue, ...]:
    match stmt:
        case gate.stmts.SingleQubitGate():
            return (stmt.qubits,)
        case gate.stmts.RotationGate():
            return (stmt.qubits,)
        case gate.stmts.ControlledGate():
            return (stmt.controls, stmt.targets)
        case gate.stmts.U3():
            return (stmt.qubits,)
        case gate.stmts.PhasedXZ():
            return (stmt.qubits,)
        case noise.stmts.SingleQubitPauliChannel():
            return (stmt.qubits,)
        case noise.stmts.Depolarize():
            return (stmt.qubits,)
        case noise.stmts.QubitLoss():
            return (stmt.qubits,)
        case noise.stmts.TwoQubitPauliChannel():
            return (stmt.controls, stmt.targets)
        case noise.stmts.Depolarize2():
            return (stmt.controls, stmt.targets)
        case noise.stmts.CorrelatedQubitLoss():
            return (stmt.qubits,)
        case qubit.stmts.Reset():
            return (stmt.qubits,)
        case qubit.stmts.Measure():
            return (stmt.qubits,)
        case _:
            return ()


def _has_empty_qubit_argument(stmt: ir.Statement) -> bool:
    return any(_is_empty_ilist(arg) for arg in _qubit_arguments(stmt))


def _method_stmts(mt: ir.Method):
    for block in mt.code.body.blocks:
        yield from block.stmts


def _callsite_input(invoke: func.Invoke, value: ir.SSAValue) -> ir.SSAValue | None:
    if not isinstance(value, ir.BlockArgument):
        return value

    args = tuple(value.owner.args)
    index = args.index(value)
    if index == 0:
        return None

    return invoke.inputs[index - 1]


def _empty_target_stmt_for_invoke(invoke: func.Invoke) -> ir.Statement | None:
    for stmt in _method_stmts(invoke.callee):
        callsite_args = tuple(
            callsite_arg
            for arg in _qubit_arguments(stmt)
            if (callsite_arg := _callsite_input(invoke, arg)) is not None
        )
        if any(_is_empty_ilist(arg) for arg in callsite_args):
            return stmt

    return None


def _insert_empty_measurements_before(node: ir.Statement) -> ir.ResultValue:
    empty_measurements = ilist.New(values=(), elem_type=MeasurementResultType)
    empty_measurements.insert_before(node)
    return empty_measurements.result


class RemoveEmptyArgGateStmts(RewriteRule):
    """Remove SQUIN statements whose statically-known qubit inputs are empty."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not _has_empty_qubit_argument(node):
            return RewriteResult()

        if isinstance(node, qubit.stmts.Measure):
            node.result.replace_by(_insert_empty_measurements_before(node))

        node.delete()
        return RewriteResult(has_done_something=True)


class RemoveEmptyArgGateInvokes(RewriteRule):
    """Remove stdlib wrapper calls whose qubit arguments are empty at the call site."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, func.Invoke):
            return RewriteResult()

        target_stmt = _empty_target_stmt_for_invoke(node)
        if target_stmt is None:
            return RewriteResult()

        if isinstance(target_stmt, qubit.stmts.Measure):
            if len(node.results) != 1:
                return RewriteResult()
            node.results[0].replace_by(_insert_empty_measurements_before(node))
        elif any(result.uses for result in node.results):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)


def _method_is_no_op(mt: ir.Method) -> bool:
    for stmt in _method_stmts(mt):
        if stmt.has_trait(ir.IsTerminator) or isinstance(stmt, func.ConstantNone):
            continue
        return False
    return True


class RemoveNoOpInvokes(RewriteRule):
    """Delete calls to methods that became empty after removing no-op gates."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, func.Invoke):
            return RewriteResult()

        if any(result.uses for result in node.results) or not _method_is_no_op(
            node.callee
        ):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)


@dataclass
class RemoveEmptyArgGates(passes.Pass):
    fold_pass: passes.Fold = field(init=False)

    def __post_init__(self):
        self.fold_pass = passes.Fold(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        result = RewriteResult()
        rule = rewrite.Fixpoint(
            rewrite.Walk(
                rewrite.Chain(
                    RemoveEmptyArgGateStmts(),
                    RemoveEmptyArgGateInvokes(),
                    DeadCodeElimination(),
                    RemoveNoOpInvokes(),
                )
            )
        )

        for _ in range(8):
            round_result = CallGraphPass(
                self.dialects, rule, no_raise=self.no_raise
            ).unsafe_run(mt)
            result = round_result.join(result)
            if not round_result.has_done_something:
                break

        return self.fold_pass(mt).join(result)
