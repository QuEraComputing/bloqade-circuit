"""This module holds the pass that rewrites jeff classical code as Python code."""

import math
from dataclasses import dataclass
from collections.abc import Callable

from kirin import ir, types
from kirin.passes import Pass
from kirin.rewrite import Walk, Chain
from kirin.dialects import py, scf, ilist
from kirin.dialects.py import len as py_len
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.math import stmts as math_stmts

from bloqade.constants import constant_int
from bloqade.jeff.types import is_subtype
from bloqade.jeff.dialects import stmts

_JEFF2PY: dict[type[ir.Statement], Callable[..., ir.Statement]] = {
    stmts.IntAdd: py.binop.Add,
    stmts.IntSub: py.binop.Sub,
    stmts.IntMul: py.binop.Mult,
    stmts.IntPow: py.binop.Pow,
    stmts.IntShl: py.binop.LShift,
    stmts.IntAnd: py.binop.BitAnd,
    stmts.IntOr: py.binop.BitOr,
    stmts.IntXor: py.binop.BitXor,
    stmts.IntAbs: py.builtin.Abs,
    stmts.IntEq: py.cmp.Eq,
    stmts.IntLtS: py.cmp.Lt,
    stmts.IntLteS: py.cmp.LtE,
    stmts.IntArrayLen: py_len.Len,
    stmts.FloatAdd: py.binop.Add,
    stmts.FloatSub: py.binop.Sub,
    stmts.FloatMul: py.binop.Mult,
    stmts.FloatPow: math_stmts.pow,
    stmts.FloatAtan2: math_stmts.atan2,
    stmts.FloatEq: py.cmp.Eq,
    stmts.FloatLt: py.cmp.Lt,
    stmts.FloatLte: py.cmp.LtE,
    stmts.FloatSqrt: math_stmts.sqrt,
    stmts.FloatAbs: math_stmts.fabs,
    stmts.FloatCeil: math_stmts.ceil,
    stmts.FloatFloor: math_stmts.floor,
    stmts.FloatExp: math_stmts.exp,
    stmts.FloatSin: math_stmts.sin,
    stmts.FloatCos: math_stmts.cos,
    stmts.FloatTan: math_stmts.tan,
    stmts.FloatAsin: math_stmts.asin,
    stmts.FloatAcos: math_stmts.acos,
    stmts.FloatAtan: math_stmts.atan,
    stmts.FloatSinh: math_stmts.sinh,
    stmts.FloatCosh: math_stmts.cosh,
    stmts.FloatTanh: math_stmts.tanh,
    stmts.FloatAsinh: math_stmts.asinh,
    stmts.FloatAtanh: math_stmts.atanh,
    stmts.FloatIsNan: math_stmts.isnan,
    stmts.FloatIsInf: math_stmts.isinf,
    stmts.FloatArrayLen: py_len.Len,
}
"""This table maps a jeff statement to the kirin statement that takes its operands."""


class _Replace(RewriteRule):
    """A rewrite rule that replaces a classical statement with one Python statement."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Replace `node` if one Python statement computes it."""
        new: ir.Statement
        if build := _JEFF2PY.get(type(node)):
            node.replace_by(build(*node.args))
            return RewriteResult(has_done_something=True)
        match node:
            case stmts.ConstInt(bitwidth=1):
                new = py.Constant(bool(node.value))
            case stmts.ConstInt():
                new = py.Constant(node.value)
            case stmts.ConstFloat():
                new = py.Constant(node.value)
            case stmts.IntNot():
                unary = (
                    py.unary.Not
                    if is_subtype(node.value.type, types.Bool)
                    else py.unary.Invert
                )
                new = unary(node.value)
            case stmts.FloatLog():
                (base := py.Constant(math.e)).insert_before(node)
                new = math_stmts.log(node.value, base.result)
            case stmts.IntArrayConst(bitwidth=1):
                bits = [bool(value) for value in node.values]
                new = py.Constant(ilist.IList(bits, elem=types.Bool))
            case stmts.IntArrayConst():
                new = py.Constant(ilist.IList(list(node.values), elem=types.Int))
            case stmts.FloatArrayConst():
                new = py.Constant(ilist.IList(list(node.values), elem=types.Float))
            case stmts.IntArrayZero(bitwidth=1) if (
                size := constant_int(node.size)
            ) is not None:
                new = py.Constant(ilist.IList([False] * size, elem=types.Bool))
            case stmts.IntArrayZero() if (size := constant_int(node.size)) is not None:
                new = py.Constant(ilist.IList([0] * size, elem=types.Int))
            case stmts.FloatArrayZero() if (
                size := constant_int(node.size)
            ) is not None:
                new = py.Constant(ilist.IList([0.0] * size, elem=types.Float))
            case stmts.IntArrayGet() | stmts.FloatArrayGet():
                # The element keeps its type, so a later rule still sees a bit.
                new = py.indexing.GetItem(node.array, node.index)
                new.result.type = node.result.type
            case stmts.IntArrayCreate(bitwidth=1):
                new = ilist.New(list(node.values), elem_type=types.Bool)
            case stmts.IntArrayCreate():
                new = ilist.New(list(node.values), elem_type=types.Int)
            case stmts.FloatArrayCreate():
                new = ilist.New(list(node.values), elem_type=types.Float)
            case _:
                return RewriteResult()
        node.replace_by(new)
        return RewriteResult(has_done_something=True)


def _conditional(
    condition: ir.SSAValue,
    yes: ir.SSAValue,
    no: ir.SSAValue,
    result_type: types.TypeAttribute,
) -> scf.IfElse:
    """Return an `scf.if` that yields `yes` or `no` by `condition`."""
    branches = []
    for chosen in (yes, no):
        block = ir.Block([scf.Yield(chosen)])
        block.args.append_from(types.Bool, "cond")
        branches.append(block)
    chosen = scf.IfElse(condition, *branches)
    chosen.results[0].type = result_type
    return chosen


class _Select(RewriteRule):
    """A rewrite rule that replaces a jeff select with an `scf.if`."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Replace `node` if it is a select."""
        if not isinstance(node, (stmts.IntSelect, stmts.FloatSelect)):
            return RewriteResult()
        node.replace_by(
            _conditional(node.condition, node.yes, node.no, node.result.type)
        )
        return RewriteResult(has_done_something=True)


class _Extremum(RewriteRule):
    """A rewrite rule that replaces a jeff minimum or maximum with an `scf.if`."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Replace `node` if it is a minimum or a maximum."""
        match node:
            case stmts.IntMinS() | stmts.FloatMin():
                maximum = False
            case stmts.IntMaxS() | stmts.FloatMax():
                maximum = True
            case _:
                return RewriteResult()
        (less := py.cmp.Lt(node.lhs, node.rhs)).insert_before(node)
        yes, no = (node.rhs, node.lhs) if maximum else (node.lhs, node.rhs)
        node.replace_by(_conditional(less.result, yes, no, node.result.type))
        return RewriteResult(has_done_something=True)


class _SignedDivision(RewriteRule):
    """A rewrite rule that divides with jeff's rounding toward zero."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Replace `node` if it is a signed division or remainder."""
        if not isinstance(node, (stmts.IntDivS, stmts.IntRemS)):
            return RewriteResult()
        a, b = node.lhs, node.rhs
        (zero := py.Constant(0)).insert_before(node)
        (remainder := py.binop.Mod(a, b)).insert_before(node)
        (nonzero := py.cmp.NotEq(remainder.result, zero.result)).insert_before(node)
        (negative_a := py.cmp.Lt(a, zero.result)).insert_before(node)
        (negative_b := py.cmp.Lt(b, zero.result)).insert_before(node)
        unlike = py.cmp.NotEq(negative_a.result, negative_b.result)
        unlike.insert_before(node)
        (fix := py.binop.BitAnd(nonzero.result, unlike.result)).insert_before(node)
        if isinstance(node, stmts.IntDivS):
            (quotient := py.binop.FloorDiv(a, b)).insert_before(node)
            node.replace_by(py.binop.Add(quotient.result, fix.result))
        else:
            (correction := py.binop.Mult(b, fix.result)).insert_before(node)
            node.replace_by(py.binop.Sub(remainder.result, correction.result))
        return RewriteResult(has_done_something=True)


class _ArrayFill(RewriteRule):
    """A rewrite rule that replaces one step of filling a known array with a list."""

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Replace `node` if it sets a constant index of a known array."""
        if not isinstance(node, (stmts.IntArraySet, stmts.FloatArraySet)):
            return RewriteResult()
        index = constant_int(node.index)
        values: list[ir.SSAValue]
        match node.array.owner:
            case py.Constant(value=value):
                constants = [py.Constant(member) for member in value.unwrap().data]
                for constant in constants:
                    constant.insert_before(node)
                values = [constant.result for constant in constants]
            case ilist.New(values=members):
                values = list(members)
            case _:
                return RewriteResult()
        if index is None or not -len(values) <= index < len(values):
            return RewriteResult()
        values[index] = node.value
        elem_type = types.Float if isinstance(node, stmts.FloatArraySet) else types.Int
        node.replace_by(ilist.New(values, elem_type=elem_type))
        return RewriteResult(has_done_something=True)


@dataclass
class JeffToPy(Pass):
    """A pass that rewrites jeff classical statements as kirin Python statements."""

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        """Rewrite every classical statement of `mt` in place."""
        rules = Chain(
            _Replace(), _Select(), _Extremum(), _SignedDivision(), _ArrayFill()
        )
        return Walk(rules).rewrite(mt.code)
