"""This module holds the jeff name or statement of each squin statement."""

from dataclasses import dataclass
from collections.abc import Callable

from kirin import ir
from kirin.dialects import py, ilist
from kirin.dialects.math import stmts as math_stmts
from kirin.dialects.ilist import stmts as ilist_stmts

from bloqade.qubit import stmts as qubit_stmts, qalloc
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.qubit.stdlib import (
    _new,
    simple as simple_qubit,
    broadcast as broadcast_qubit,
)
from bloqade.jeff.dialects import stmts
from bloqade.squin.stdlib.simple import gate as simple_gate
from bloqade.squin.stdlib.broadcast import gate as broadcast_gate

EMIT_KEY = "emit.squin2jeff"
"""The registry key of the rules that emit jeff statements for squin statements."""


@dataclass(frozen=True)
class GateForm:
    """The jeff gate that a squin gate applies to each qubit, or group of qubits."""

    name: str
    angles: int = 0
    """The number of leading angle operands, in radians for a library kernel."""
    controls: int = 0
    """The number of control operands, which come before the target operands."""
    adjoint: bool = False


_FORMS = {
    "x": GateForm("x"),
    "y": GateForm("y"),
    "z": GateForm("z"),
    "h": GateForm("h"),
    "s": GateForm("s"),
    "t": GateForm("t"),
    "sqrt_x": GateForm("sqrt_x"),
    "sqrt_y": GateForm("sqrt_y"),
    "sqrt_z": GateForm("s"),
    "s_adj": GateForm("s", adjoint=True),
    "t_adj": GateForm("t", adjoint=True),
    "sqrt_x_adj": GateForm("sqrt_x", adjoint=True),
    "sqrt_y_adj": GateForm("sqrt_y", adjoint=True),
    "sqrt_z_adj": GateForm("s", adjoint=True),
    "rx": GateForm("rx", angles=1),
    "ry": GateForm("ry", angles=1),
    "rz": GateForm("rz", angles=1),
    "u3": GateForm("u", angles=3),
    "cx": GateForm("x", controls=1),
    "cy": GateForm("y", controls=1),
    "cz": GateForm("z", controls=1),
    "ccz": GateForm("z", controls=2),
    "swap": GateForm("swap"),
}
"""The jeff gate of each squin library gate kernel, by the name of the kernel."""

GATE_KERNELS: dict[ir.Method, GateForm] = {
    getattr(module, name): form
    for module in (simple_gate, broadcast_gate)
    for name, form in _FORMS.items()
}
"""The jeff gate of each squin library gate kernel, on one qubit or on a list."""

GATES: dict[type[ir.Statement], GateForm] = {
    gate_stmts.X: _FORMS["x"],
    gate_stmts.Y: _FORMS["y"],
    gate_stmts.Z: _FORMS["z"],
    gate_stmts.H: _FORMS["h"],
    gate_stmts.S: _FORMS["s"],
    gate_stmts.T: _FORMS["t"],
    gate_stmts.SqrtX: _FORMS["sqrt_x"],
    gate_stmts.SqrtY: _FORMS["sqrt_y"],
    gate_stmts.Rx: _FORMS["rx"],
    gate_stmts.Ry: _FORMS["ry"],
    gate_stmts.Rz: _FORMS["rz"],
    gate_stmts.U3: _FORMS["u3"],
    gate_stmts.CX: _FORMS["cx"],
    gate_stmts.CY: _FORMS["cy"],
    gate_stmts.CZ: _FORMS["cz"],
    gate_stmts.CCZ: _FORMS["ccz"],
    gate_stmts.Swap: _FORMS["swap"],
}
"""The jeff gate of each squin gate statement, whose angles are in turns."""

QUBIT_KERNELS: dict[ir.Method, type[ir.Statement]] = {
    _new.new: qubit_stmts.New,
    simple_qubit.reset: qubit_stmts.Reset,
    broadcast_qubit.reset: qubit_stmts.Reset,
    simple_qubit.measure: qubit_stmts.Measure,
    broadcast_qubit.measure: qubit_stmts.Measure,
    simple_qubit.is_zero: qubit_stmts.IsZero,
    broadcast_qubit.is_zero: qubit_stmts.IsZero,
    simple_qubit.is_one: qubit_stmts.IsOne,
    broadcast_qubit.is_one: qubit_stmts.IsOne,
}
"""The qubit statement that each squin library qubit kernel wraps."""


Binary = Callable[[ir.SSAValue, ir.SSAValue], ir.Statement]
Unary = Callable[[ir.SSAValue], ir.Statement]

INT_BINARY: dict[type[ir.Statement], Binary] = {
    py.binop.Add: stmts.IntAdd,
    py.binop.Sub: stmts.IntSub,
    py.binop.Mult: stmts.IntMul,
    py.binop.Pow: stmts.IntPow,
    py.binop.LShift: stmts.IntShl,
    py.binop.BitAnd: stmts.IntAnd,
    py.binop.BitOr: stmts.IntOr,
    py.binop.BitXor: stmts.IntXor,
    py.cmp.Eq: stmts.IntEq,
    py.cmp.NotEq: stmts.IntEq,
    py.cmp.Lt: stmts.IntLtS,
    py.cmp.LtE: stmts.IntLteS,
}
"""The jeff statement of each squin statement on two integers.

A `!=` is the negation of the equality. Floor division and modulo have their
own rule, since jeff rounds toward zero.
"""

FLOAT_BINARY: dict[type[ir.Statement], Binary] = {
    py.binop.Add: stmts.FloatAdd,
    py.binop.Sub: stmts.FloatSub,
    py.binop.Mult: stmts.FloatMul,
    py.binop.Pow: stmts.FloatPow,
    math_stmts.pow: stmts.FloatPow,
    math_stmts.atan2: stmts.FloatAtan2,
    py.cmp.Eq: stmts.FloatEq,
    py.cmp.NotEq: stmts.FloatEq,
    py.cmp.Lt: stmts.FloatLt,
    py.cmp.LtE: stmts.FloatLte,
}
"""The jeff statement of each squin statement on two floats.

A `!=` is the negation of the equality.
"""

SWAPPED: dict[type[ir.Statement], type[ir.Statement]] = {
    py.cmp.Gt: py.cmp.Lt,
    py.cmp.GtE: py.cmp.LtE,
}
"""The comparison that computes each reversed comparison with swapped operands."""

FLOAT_UNARY: dict[type[ir.Statement], Unary] = {
    math_stmts.sqrt: stmts.FloatSqrt,
    math_stmts.fabs: stmts.FloatAbs,
    math_stmts.ceil: stmts.FloatCeil,
    math_stmts.floor: stmts.FloatFloor,
    math_stmts.exp: stmts.FloatExp,
    math_stmts.sin: stmts.FloatSin,
    math_stmts.cos: stmts.FloatCos,
    math_stmts.tan: stmts.FloatTan,
    math_stmts.asin: stmts.FloatAsin,
    math_stmts.acos: stmts.FloatAcos,
    math_stmts.atan: stmts.FloatAtan,
    math_stmts.sinh: stmts.FloatSinh,
    math_stmts.cosh: stmts.FloatCosh,
    math_stmts.tanh: stmts.FloatTanh,
    math_stmts.asinh: stmts.FloatAsinh,
    math_stmts.atanh: stmts.FloatAtanh,
    math_stmts.isnan: stmts.FloatIsNan,
    math_stmts.isinf: stmts.FloatIsInf,
}
"""The jeff statement of each squin statement on one float."""


def loop_range(iterable: ir.SSAValue) -> ilist_stmts.Range | range | None:
    """Return the range that a loop over `iterable` runs over, or None.

    The range is a `range` statement, or a Python range that a constant holds.
    """
    match iterable.owner:
        case ilist_stmts.Range() as stmt:
            return stmt
        case py.Constant(value=value) if isinstance(
            data := value.unwrap(), ilist.IList
        ) and isinstance(data.data, range):
            return data.data
    return None


def is_library(kernel: ir.Method) -> bool:
    """Return True if `kernel` is a squin library kernel that becomes jeff statements.

    A library kernel is a gate kernel, a qubit kernel or `qalloc`.
    """
    return kernel in GATE_KERNELS or kernel in QUBIT_KERNELS or kernel is qalloc
