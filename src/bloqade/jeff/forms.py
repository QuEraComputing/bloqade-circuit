"""Map each squin and wire statement to its Jeff name or statement."""

from dataclasses import dataclass
from collections.abc import Callable

from kirin import ir
from kirin.dialects import py, ilist
from kirin.dialects.math import stmts as math_stmts
from kirin.dialects.ilist import stmts as ilist_stmts

from bloqade.qubit import stmts as qubit_stmts, qalloc
from bloqade.squin.wire import stmts as wire
from bloqade.qubit.stdlib import (
    _new,
    simple as simple_qubit,
    broadcast as broadcast_qubit,
)
from bloqade.jeff.dialects import stmts
from bloqade.squin.wire.kinds import GateKind
from bloqade.squin.stdlib.simple import gate as simple_gate
from bloqade.squin.stdlib.broadcast import gate as broadcast_gate

EMIT_KEY = "emit.squin2jeff"
"""Hold the registry key of the rules that emit jeff statements for squin statements."""


@dataclass(frozen=True)
class GateForm:
    """The jeff gate that a squin gate applies to each qubit, or group of qubits."""

    name: str
    angles: int = 0
    """Hold the number of leading angle operands, in radians for a library kernel."""
    controls: int = 0
    """Hold the number of control operands, which come before the target operands."""
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
"""Hold the jeff gate of each squin library gate kernel, by the name of the kernel."""

GATE_KERNELS: dict[ir.Method, GateForm] = {
    kernel: form
    for simple, broadcast, form in (
        (simple_gate.x, broadcast_gate.x, _FORMS["x"]),
        (simple_gate.y, broadcast_gate.y, _FORMS["y"]),
        (simple_gate.z, broadcast_gate.z, _FORMS["z"]),
        (simple_gate.h, broadcast_gate.h, _FORMS["h"]),
        (simple_gate.s, broadcast_gate.s, _FORMS["s"]),
        (simple_gate.t, broadcast_gate.t, _FORMS["t"]),
        (simple_gate.sqrt_x, broadcast_gate.sqrt_x, _FORMS["sqrt_x"]),
        (simple_gate.sqrt_y, broadcast_gate.sqrt_y, _FORMS["sqrt_y"]),
        (simple_gate.sqrt_z, broadcast_gate.sqrt_z, _FORMS["sqrt_z"]),
        (simple_gate.s_adj, broadcast_gate.s_adj, _FORMS["s_adj"]),
        (simple_gate.t_adj, broadcast_gate.t_adj, _FORMS["t_adj"]),
        (simple_gate.sqrt_x_adj, broadcast_gate.sqrt_x_adj, _FORMS["sqrt_x_adj"]),
        (simple_gate.sqrt_y_adj, broadcast_gate.sqrt_y_adj, _FORMS["sqrt_y_adj"]),
        (simple_gate.sqrt_z_adj, broadcast_gate.sqrt_z_adj, _FORMS["sqrt_z_adj"]),
        (simple_gate.rx, broadcast_gate.rx, _FORMS["rx"]),
        (simple_gate.ry, broadcast_gate.ry, _FORMS["ry"]),
        (simple_gate.rz, broadcast_gate.rz, _FORMS["rz"]),
        (simple_gate.u3, broadcast_gate.u3, _FORMS["u3"]),
        (simple_gate.cx, broadcast_gate.cx, _FORMS["cx"]),
        (simple_gate.cy, broadcast_gate.cy, _FORMS["cy"]),
        (simple_gate.cz, broadcast_gate.cz, _FORMS["cz"]),
        (simple_gate.ccz, broadcast_gate.ccz, _FORMS["ccz"]),
        (simple_gate.swap, broadcast_gate.swap, _FORMS["swap"]),
    )
    for kernel in (simple, broadcast)
}
"""Map each squin library gate directly to its Jeff form."""


GATES: dict[GateKind, GateForm] = {
    GateKind.X: _FORMS["x"],
    GateKind.Y: _FORMS["y"],
    GateKind.Z: _FORMS["z"],
    GateKind.H: _FORMS["h"],
    GateKind.S: _FORMS["s"],
    GateKind.T: _FORMS["t"],
    GateKind.SQRT_X: _FORMS["sqrt_x"],
    GateKind.SQRT_Y: _FORMS["sqrt_y"],
    GateKind.RX: _FORMS["rx"],
    GateKind.RY: _FORMS["ry"],
    GateKind.RZ: _FORMS["rz"],
    GateKind.U3: _FORMS["u3"],
    GateKind.CX: _FORMS["cx"],
    GateKind.CY: _FORMS["cy"],
    GateKind.CZ: _FORMS["cz"],
    GateKind.CCZ: _FORMS["ccz"],
    GateKind.SWAP: _FORMS["swap"],
    # The native Rz and CZ are the same gates as the squin Rz and CZ. The native Rz
    # also takes its angle in turns.
    GateKind.NATIVE_RZ: _FORMS["rz"],
    GateKind.NATIVE_CZ: _FORMS["cz"],
}
"""Hold the jeff gate of each wire gate kind, whose angles are in turns.

Each entry is the same gate in both forms. A gate without an equal Jeff gate, such
as the native `R`, has no entry.
"""

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
"""Hold the qubit statement that each squin library qubit kernel wraps."""


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
"""Hold the jeff statement of each squin statement on two integers.

A `!=` is the negation of the equality. Floor division and modulo have their
own rule, since jeff rounds toward zero.
"""

FLOAT_BINARY: dict[type[ir.Statement], Binary] = {
    py.binop.Add: stmts.FloatAdd,
    py.binop.Sub: stmts.FloatSub,
    py.binop.Mult: stmts.FloatMul,
    py.binop.Div: stmts.FloatDiv,
    py.binop.Pow: stmts.FloatPow,
    math_stmts.pow: stmts.FloatPow,
    math_stmts.atan2: stmts.FloatAtan2,
    py.cmp.Eq: stmts.FloatEq,
    py.cmp.NotEq: stmts.FloatEq,
    py.cmp.Lt: stmts.FloatLt,
    py.cmp.LtE: stmts.FloatLte,
}
"""Hold the jeff statement of each squin statement on two floats.

A `!=` is the negation of the equality.
"""

SWAPPED: dict[type[ir.Statement], type[ir.Statement]] = {
    py.cmp.Gt: py.cmp.Lt,
    py.cmp.GtE: py.cmp.LtE,
}
"""Hold the comparison that computes each reversed comparison with swapped operands."""

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
"""Hold the jeff statement of each squin statement on one float."""


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


WIRE_TO_JEFF: dict[type[ir.Statement], type[ir.Statement]] = {
    wire.Alloc: stmts.Alloc,
    wire.Free: stmts.Free,
    wire.FreeRegister: stmts.RegFree,
    wire.Borrow: stmts.Extract,
    wire.Release: stmts.Insert,
    wire.Length: stmts.RegLength,
    wire.Take: stmts.Extract,
    wire.Put: stmts.Insert,
    wire.TakeSlice: stmts.ExtractSlice,
    wire.PutSlice: stmts.InsertSlice,
    wire.SplitRegister: stmts.RegSplit,
    wire.JoinRegister: stmts.RegJoin,
    wire.DiscardRegister: stmts.RegFree,
}
"""Map each wire statement to the Jeff statement with the same operands and results.

Jeff has one extraction for a borrow and a take, and one insertion for a release
and a put.
"""

JEFF_TO_WIRE: dict[type[ir.Statement], Callable[..., ir.Statement]] = {
    stmts.Alloc: wire.Alloc,
    stmts.Free: wire.Free,
    stmts.FreeZero: wire.Free,
    stmts.RegAlloc: wire.AllocRegister,
    stmts.RegFree: wire.DiscardRegister,
    stmts.RegFreeZero: wire.DiscardRegister,
    stmts.Extract: wire.Take,
    stmts.Insert: wire.Put,
    stmts.ExtractSlice: wire.TakeSlice,
    stmts.InsertSlice: wire.PutSlice,
    stmts.RegSplit: wire.SplitRegister,
    stmts.RegJoin: wire.JoinRegister,
    stmts.RegLength: wire.Length,
    stmts.Reset: wire.Reset,
}
"""Map each Jeff statement to the wire statement with the same operands and results.

A Jeff extraction becomes a take and an insertion a put, because a Jeff program
can insert a wire at another index than the one that it came from. A Jeff register
free can find elements out of the register, so it becomes `DiscardRegister`.
"""
