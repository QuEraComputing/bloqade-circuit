"""This module holds the validation pass for jeff code that squin cannot express."""

from dataclasses import dataclass

from kirin import ir, interp
from kirin.lattice import EmptyLattice
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.constants import constant_int
from bloqade.jeff.gates import canonical
from bloqade.jeff.types import is_bit
from bloqade.jeff.dialects import stmts, kernel as jeff_kernel

from ..base import SHARED_KEY, Check
from .gates import gate_supported

KEY = "jeff.to_squin"
"""The registry key of the rules that refuse what squin cannot express."""


def fill_length(array: ir.SSAValue) -> int | None:
    """Return the length of an array that constant sets fill, or None.

    The array is a constant array, an array of zeros of constant size, or a set at
    a constant index on such an array that nothing else reads.
    """
    match array.owner:
        case stmts.IntArrayConst(values=values) | stmts.FloatArrayConst(values=values):
            return len(values)
        case stmts.IntArrayZero(size=size) | stmts.FloatArrayZero(size=size):
            return constant_int(size)
        case stmts.IntArraySet(array=earlier, index=index) | stmts.FloatArraySet(
            array=earlier, index=index
        ):
            if constant_int(index) is None or len(earlier.uses) != 1:
                return None
            return fill_length(earlier)
    return None


@dataclass
class JeffToSquinAnalysis(Check[EmptyLattice]):
    """An analysis that reports each jeff construct that squin cannot express."""

    keys = (KEY, SHARED_KEY)
    lattice = EmptyLattice

    def refuse(self, node: ir.Statement, message: str) -> None:
        """Record that squin cannot express `node`."""
        self.add_validation_error(node, ir.ValidationError(node, message))


@stmts.gate.dialect.register(key=KEY)
class _Gates(interp.MethodTable):
    """A method table that refuses the gates that squin has no statement for."""

    @interp.impl(stmts.Ppr)
    def ppr(
        self,
        check: JeffToSquinAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: stmts.Ppr,
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse a Pauli-product rotation."""
        check.refuse(stmt, "squin has no Pauli-product rotation statement")
        return check.eval_fallback(frame, stmt)

    @interp.impl(stmts.Gate)
    def gate(
        self,
        check: JeffToSquinAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: stmts.Gate,
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse a gate whose shape squin has no statement for."""
        if not gate_supported(shape := canonical(stmt)):
            check.refuse(
                stmt,
                f"gate '{stmt.gate_name}' has no squin statement. It reads as "
                f"{shape.name} with {len(shape.controls)} controls and power "
                f"{shape.power}.",
            )
        return check.eval_fallback(frame, stmt)


@stmts.classical.dialect.register(key=KEY)
class _Classical(interp.MethodTable):
    """A method table that refuses classical statements that squin cannot express."""

    @interp.impl(stmts.IntDivU)
    @interp.impl(stmts.IntRemU)
    @interp.impl(stmts.IntShr)
    @interp.impl(stmts.IntLtU)
    @interp.impl(stmts.IntLteU)
    @interp.impl(stmts.IntMinU)
    @interp.impl(stmts.IntMaxU)
    def unsigned(
        self,
        check: JeffToSquinAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: ir.Statement,
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse an unsigned integer operation."""
        check.refuse(
            stmt,
            f"squin integers have no unsigned form for '{stmt.name}'. Squin reads "
            "every integer as a signed value.",
        )
        return check.eval_fallback(frame, stmt)

    @interp.impl(stmts.IntAdd)
    @interp.impl(stmts.IntSub)
    @interp.impl(stmts.IntMul)
    @interp.impl(stmts.IntDivS)
    @interp.impl(stmts.IntPow)
    @interp.impl(stmts.IntMinS)
    @interp.impl(stmts.IntMaxS)
    @interp.impl(stmts.IntRemS)
    @interp.impl(stmts.IntShl)
    def arithmetic(
        self,
        check: JeffToSquinAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: stmts.IntBinary,
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse arithmetic on a bit, which squin types as a measurement result."""
        if is_bit(stmt.lhs) or is_bit(stmt.rhs):
            check.refuse(
                stmt,
                f"'{stmt.name}' on a bit has no squin form. Squin types a "
                "measurement result as a bit.",
            )
        return check.eval_fallback(frame, stmt)

    @interp.impl(stmts.IntArraySet)
    @interp.impl(stmts.FloatArraySet)
    def array_set(
        self,
        check: JeffToSquinAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: stmts.IntArraySet | stmts.FloatArraySet,
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse a set that is not a fill of a known array at a constant index."""
        index, length = constant_int(stmt.index), fill_length(stmt.array)
        if index is None or length is None or len(stmt.array.uses) != 1:
            check.refuse(
                stmt,
                f"squin has no mutable array for '{stmt.name}'. Squin can express "
                "only a fill of a known array at constant indices.",
            )
        elif not -length <= index < length:
            check.refuse(
                stmt, f"index {index} lies outside the {length} slots of the array"
            )
        return check.eval_fallback(frame, stmt)

    @interp.impl(stmts.IntArrayZero)
    @interp.impl(stmts.FloatArrayZero)
    def array_zero(
        self,
        check: JeffToSquinAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: stmts.IntArrayZero | stmts.FloatArrayZero,
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse an array of runtime length."""
        if constant_int(stmt.size) is None:
            check.refuse(
                stmt, f"squin has no array of runtime length for '{stmt.name}'"
            )
        return check.eval_fallback(frame, stmt)

    @interp.impl(stmts.FloatAcosh)
    def acosh(
        self,
        check: JeffToSquinAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: stmts.FloatAcosh,
    ) -> interp.StatementResult[EmptyLattice]:
        """Refuse acosh, which squin's math dialect lacks."""
        check.refuse(stmt, "squin's math dialect has no acosh")
        return check.eval_fallback(frame, stmt)


@stmts.scf.dialect.register(key=KEY)
class _Scf(interp.MethodTable):
    """A method table that refuses while loops."""

    @interp.impl(stmts.While)
    def while_(
        self,
        check: JeffToSquinAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: stmts.While,
    ) -> tuple[EmptyLattice, ...]:
        """Refuse the loop, then check its regions."""
        check.refuse(stmt, "squin cannot express while loops")
        return check.run_regions(frame, stmt)


@dataclass
class JeffToSquinValidation(ValidationPass[ForwardFrame[EmptyLattice]]):
    """A validation pass that reports every jeff construct that squin cannot express."""

    def name(self) -> str:
        """Return the pass name that refusals show."""
        return "JeffToSquin"

    def run(
        self, method: ir.Method
    ) -> tuple[ForwardFrame[EmptyLattice], list[ir.ValidationError]]:
        """Run the conversion analysis on `method` and every function that it calls."""
        analysis = JeffToSquinAnalysis(jeff_kernel)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
