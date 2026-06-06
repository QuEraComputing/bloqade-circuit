"""Helpers for emitting measurement-conditioned ``scf.IfElse`` statements as
Cirq classical controls (``cirq.ClassicallyControlledOperation``).

The single source of truth for *which* ``if`` shapes can be emitted lives in
:func:`trace_condition`. Both the validation pass (``validation.py``) and the
emit method table (``scf.py``) call it so that validation and emission can never
disagree.
"""

import sympy
from kirin import ir
from kirin.dialects import py, ilist

from bloqade.qubit import stmts as qubit_stmts


class ConditionError(Exception):
    """Raised when an ``scf.IfElse`` condition cannot be expressed as a Cirq
    classical control."""


def _const_bit(value: ir.SSAValue) -> int | None:
    """Return ``0``/``1`` if ``value`` is a constant ``0``/``1``/``False``/``True``,
    else ``None``."""
    if isinstance(value, ir.ResultValue) and isinstance(value.owner, py.Constant):
        data = value.owner.value.unwrap()
        if isinstance(data, bool):
            return int(data)
        if data == 0:
            return 0
        if data == 1:
            return 1
    return None


def _trace_cmp(
    stmt: "py.cmp.Eq | py.cmp.NotEq", polarity: int, *, eq: bool
) -> tuple[ir.SSAValue, int]:
    lhs_bit = _const_bit(stmt.lhs)
    rhs_bit = _const_bit(stmt.rhs)
    if lhs_bit is not None and rhs_bit is None:
        bit, other = lhs_bit, stmt.rhs
    elif rhs_bit is not None and lhs_bit is None:
        bit, other = rhs_bit, stmt.lhs
    else:
        raise ConditionError(
            "comparison condition must compare a measurement to a constant "
            "0, 1, False or True"
        )
    # `polarity` == 1 means "control fires when the measured qubit is |1>".
    # eq & bit==1  -> fire on |1> (keep);   eq & bit==0  -> fire on |0> (flip)
    # neq & bit==1 -> fire on |0> (flip);   neq & bit==0 -> fire on |1> (keep)
    keep = (bit == 1) == eq
    new_polarity = polarity if keep else 1 - polarity
    return trace_condition(other, new_polarity)


def trace_condition(cond: ir.SSAValue, polarity: int = 1) -> tuple[ir.SSAValue, int]:
    """Walk the SSA def-chain of an ``scf.IfElse`` condition back to the
    ``qubit.Measure`` it derives from.

    Returns ``(measure_result, polarity)`` where ``measure_result`` is the SSA
    value produced by the originating ``qubit.Measure`` statement and
    ``polarity`` is ``1`` if the control fires when the qubit is measured in
    ``|1>`` and ``0`` if it fires on ``|0>``.

    Raises :class:`ConditionError` for any shape that has no Cirq
    classical-control equivalent.
    """
    if not isinstance(cond, ir.ResultValue):
        raise ConditionError(
            "condition must derive from a measurement, but is a block argument"
        )

    owner = cond.owner

    if isinstance(owner, qubit_stmts.Measure):
        return cond, polarity
    if isinstance(owner, qubit_stmts.IsOne):
        return trace_condition(owner.measurements, polarity)
    if isinstance(owner, qubit_stmts.IsZero):
        return trace_condition(owner.measurements, 1 - polarity)
    if isinstance(owner, qubit_stmts.IsLost):
        raise ConditionError(
            "the is_lost predicate has no Cirq classical-control equivalent"
        )
    if isinstance(owner, py.indexing.GetItem):
        return trace_condition(owner.obj, polarity)
    if isinstance(owner, ilist.New):
        if len(owner.values) != 1:
            raise ConditionError(
                "only conditions based on a single measurement are supported"
            )
        return trace_condition(owner.values[0], polarity)
    if isinstance(owner, ilist.Foldl):
        # produced by load_circuit when importing a Cirq classical control:
        # foldl(or, measurement_results, init=False) reduces a length-1 list.
        return trace_condition(owner.collection, polarity)
    if isinstance(owner, py.cmp.Eq):
        return _trace_cmp(owner, polarity, eq=True)
    if isinstance(owner, py.cmp.NotEq):
        return _trace_cmp(owner, polarity, eq=False)

    raise ConditionError(
        f"unsupported condition statement '{type(owner).__name__}'; the "
        "condition must be a single measurement compared to 0/1 or wrapped in "
        "is_one/is_zero"
    )


def measure_num_qubits(measure_result: ir.SSAValue) -> int | None:
    """Best-effort count of qubits feeding the originating ``qubit.Measure``.

    Returns ``None`` if it cannot be determined statically."""
    owner = measure_result.owner
    if not isinstance(owner, qubit_stmts.Measure):
        return None
    qubits = owner.qubits
    if isinstance(qubits, ir.ResultValue) and isinstance(qubits.owner, ilist.New):
        return len(qubits.owner.values)
    return None


def build_cirq_condition(key: str, polarity: int):
    """Build the Cirq classical-control condition for a measurement ``key``.

    ``polarity == 1`` -> fire on ``|1>`` (a Cirq ``KeyCondition``, expressed as
    the bare key string). ``polarity == 0`` -> fire on ``|0>`` (a
    ``SympyCondition`` ``Eq(key, 0)``)."""
    if polarity == 1:
        return key
    return sympy.Eq(sympy.Symbol(key), 0)
