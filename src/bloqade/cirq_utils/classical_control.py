from dataclasses import dataclass

import cirq
from kirin import ir, types
from kirin.dialects import py, scf, ilist

from bloqade.qubit import stmts as qubit
from bloqade.squin import gate

_ALLOWED_CMP_VALUES = {0, 1, True, False}


@dataclass(frozen=True)
class ClassicalIfCondition:
    measure: qubit.Measure
    trigger_on_one: bool


def _unwrap_constant(ssa: ir.SSAValue) -> object | None:
    if not isinstance(ssa, ir.ResultValue):
        return None
    owner = ssa.owner
    if isinstance(owner, py.Constant):
        return owner.value.unwrap()
    return None


def _resolve_measure_stmt(ssa: ir.SSAValue) -> qubit.Measure | None:
    if not isinstance(ssa, ir.ResultValue):
        return None
    owner = ssa.owner
    if isinstance(owner, (py.GetItem, py.indexing.GetItem)):
        return _resolve_measure_stmt(owner.obj)
    if isinstance(owner, qubit.Measure):
        return owner
    return None


def _resolve_bare_measure(ssa: ir.SSAValue) -> qubit.Measure | None:
    if not isinstance(ssa, ir.ResultValue):
        return None
    owner = ssa.owner
    if isinstance(owner, qubit.Measure):
        return owner
    if isinstance(owner, (py.GetItem, py.indexing.GetItem)):
        return _resolve_bare_measure(owner.obj)
    # AggressiveUnroll wraps individual results back into a single-element IList
    # before passing to is_one/is_zero, so trace through it.
    if isinstance(owner, ilist.New) and len(owner.values) == 1:
        return _resolve_bare_measure(owner.values[0])
    return None


def _resolve_predicate_chain(
    ssa: ir.SSAValue,
) -> tuple[qubit.Measure, bool] | None:
    if not isinstance(ssa, ir.ResultValue):
        return None
    owner = ssa.owner
    if isinstance(owner, (py.GetItem, py.indexing.GetItem)):
        return _resolve_predicate_chain(owner.obj)
    if isinstance(owner, qubit.IsOne):
        m = _resolve_bare_measure(owner.measurements)
        return (m, True) if m is not None else None
    if isinstance(owner, qubit.IsZero):
        m = _resolve_bare_measure(owner.measurements)
        return (m, False) if m is not None else None
    return None


def is_single_qubit_measure(measure: qubit.Measure) -> bool:
    qubits_type = measure.qubits.type
    if not hasattr(qubits_type, "vars") or len(qubits_type.vars) < 2:
        return False
    len_type = qubits_type.vars[1]
    return isinstance(len_type, types.Literal) and len_type.data == 1


def parse_classical_if_condition(cond: ir.SSAValue) -> ClassicalIfCondition | None:
    if not isinstance(cond, ir.ResultValue):
        return None
    owner = cond.owner

    if isinstance(owner, py.cmp.Eq):
        measure = _resolve_measure_stmt(owner.lhs)
        cmp_val = _unwrap_constant(owner.rhs)
        if measure is None:
            measure = _resolve_measure_stmt(owner.rhs)
            cmp_val = _unwrap_constant(owner.lhs)
        if measure is None or cmp_val not in _ALLOWED_CMP_VALUES:
            return None
        return ClassicalIfCondition(
            measure=measure,
            trigger_on_one=cmp_val in (1, True),
        )

    if isinstance(owner, py.cmp.NotEq):
        measure = _resolve_measure_stmt(owner.lhs)
        cmp_val = _unwrap_constant(owner.rhs)
        if measure is None:
            measure = _resolve_measure_stmt(owner.rhs)
            cmp_val = _unwrap_constant(owner.lhs)
        if measure is None or cmp_val not in _ALLOWED_CMP_VALUES:
            return None
        # != flips the polarity relative to ==
        return ClassicalIfCondition(
            measure=measure,
            trigger_on_one=cmp_val not in (1, True),
        )

    result = _resolve_predicate_chain(cond)
    if result is not None:
        measure, trigger_on_one = result
        return ClassicalIfCondition(measure=measure, trigger_on_one=trigger_on_one)

    return None


def is_is_lost_condition(cond: ir.SSAValue) -> bool:
    if not isinstance(cond, ir.ResultValue):
        return False
    owner = cond.owner
    if isinstance(owner, (py.GetItem, py.indexing.GetItem)):
        return is_is_lost_condition(owner.obj)
    return isinstance(owner, qubit.IsLost)


def is_empty_else(stmt: scf.IfElse) -> bool:
    if not stmt.else_body.blocks:
        return True
    else_stmts = list(stmt.else_body.blocks[0].stmts)
    return (
        len(else_stmts) == 1
        and isinstance(else_stmts[0], scf.Yield)
        and len(else_stmts[0].values) == 0
    )


def get_single_gate(stmt: scf.IfElse) -> gate.stmts.Gate | None:
    if not stmt.then_body.blocks:
        return None

    then_stmts = list(stmt.then_body.blocks[0].stmts)
    if len(then_stmts) < 2:
        return None

    term = then_stmts[-1]
    if not isinstance(term, scf.Yield) or len(term.values) != 0:
        return None

    body_stmts = then_stmts[:-1]
    gates = [s for s in body_stmts if isinstance(s, gate.stmts.Gate)]
    if len(gates) != 1:
        return None

    allowed_non_gate = (
        qubit.New,
        ilist.New,
        py.Constant,
        py.GetItem,
        py.indexing.GetItem,
    )
    for s in body_stmts:
        if isinstance(s, gate.stmts.Gate):
            continue
        if not isinstance(s, allowed_non_gate):
            return None

    return gates[0]


def classical_control_for_condition(
    key: str, condition: ClassicalIfCondition
) -> cirq.Condition:
    return cirq.BitMaskKeyCondition(
        key,
        target_value=int(condition.trigger_on_one),
        equal_target=True,
        bitmask=1,
    )
