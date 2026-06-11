from dataclasses import dataclass

import cirq
import sympy
from kirin import ir, interp
from kirin.dialects import py

from bloqade.qubit import stmts as qubit


@dataclass(frozen=True)
class MeasurementCondition:
    measurement: ir.SSAValue
    value: bool


def _constant_value(value: ir.SSAValue):
    if not isinstance(value, ir.ResultValue) or not isinstance(value.owner, py.Constant):
        return None
    return value.owner.value.unwrap()


def _measurement_result(value: ir.SSAValue) -> ir.SSAValue | None:
    if not isinstance(value, ir.ResultValue):
        return None

    owner = value.owner
    if isinstance(owner, py.indexing.GetItem):
        index = _constant_value(owner.index)
        if index != 0:
            return None

        if isinstance(owner.obj, ir.ResultValue) and isinstance(
            owner.obj.owner, qubit.Measure
        ):
            qubits = owner.obj.owner.qubits
            if (
                isinstance(qubits, ir.ResultValue)
                and isinstance(qubits.owner, py.indexing.GetItem)
            ):
                return owner.obj
            if (
                hasattr(qubits, "owner")
                and hasattr(qubits.owner, "values")
                and len(qubits.owner.values) == 1
            ):
                return owner.obj

    return None


def get_measurement_condition(cond: ir.SSAValue) -> MeasurementCondition | None:
    if not isinstance(cond, ir.ResultValue):
        return None

    owner = cond.owner
    if isinstance(owner, py.cmp.Eq):
        lhs_measurement = _measurement_result(owner.lhs)
        rhs_value = _constant_value(owner.rhs)
        if lhs_measurement is not None and rhs_value in (0, 1, False, True):
            return MeasurementCondition(lhs_measurement, bool(rhs_value))

        rhs_measurement = _measurement_result(owner.rhs)
        lhs_value = _constant_value(owner.lhs)
        if rhs_measurement is not None and lhs_value in (0, 1, False, True):
            return MeasurementCondition(rhs_measurement, bool(lhs_value))

    return None


def cirq_condition_for_key(key: str, value: bool):
    if value:
        return key
    return cirq.SympyCondition(sympy.Eq(sympy.Symbol(key), 0))


def unsupported_condition_error() -> interp.exceptions.InterpreterError:
    return interp.exceptions.InterpreterError(
        "Cirq emission supports if statements only when the condition compares "
        "one measurement result with True, False, 1, or 0."
    )
