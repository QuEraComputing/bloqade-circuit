from typing import Any

from kirin import ir, types, interp
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.dialects import py, scf, func
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame
from kirin.dialects.ilist.stmts import Range as IListRange

from bloqade.qubit import stmts as qubit_stmts
from bloqade.squin import gate
from bloqade.types import MeasurementResultType

PauliGateType = (gate.stmts.X, gate.stmts.Y, gate.stmts.Z)


def _is_supported_iterable(ssa: ir.SSAValue) -> bool:
    """True if the loop iterable is `range(n)` with a positive constant `n`.

    Stim kernels support only the single-arg `range(n)` form. Multi-arg
    ranges (start != 0 or step != 1), zero-count ranges, runtime counts,
    and non-range iterables are all rejected.

    Recognizes two IR shapes:
      - py.Constant whose value is a `range` (or IList wrapping one) —
        post-fold representation produced by const-prop.
      - py.range.Range / ilist.Range with all-Constant start/stop/step —
        pre-fold representation.
    """
    if not isinstance(ssa, ir.ResultValue):
        return False
    owner = ssa.owner
    if isinstance(owner, py.Constant):
        value = owner.value.unwrap()
        if hasattr(value, "data") and isinstance(value.data, range):
            r = value.data
        elif isinstance(value, range):
            r = value
        else:
            return False
        return r.start == 0 and r.stop >= 1 and r.step == 1
    if isinstance(owner, (py.range.Range, IListRange)):
        if not all(
            isinstance(a, ir.ResultValue) and isinstance(a.owner, py.Constant)
            for a in (owner.start, owner.stop, owner.step)
        ):
            return False
        start = owner.start.owner.value.unwrap()
        stop = owner.stop.owner.value.unwrap()
        step = owner.step.owner.value.unwrap()
        return start == 0 and stop >= 1 and step == 1
    return False


class _StimFromSquinValidationAnalysis(Forward[EmptyLattice]):
    keys = ["stim.validate.from_squin"]

    lattice = EmptyLattice

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        return tuple(self.lattice.bottom() for _ in range(len(node.results)))


@scf.dialect.register(key="stim.validate.from_squin")
class _ScfMethods(interp.MethodTable):

    @interp.impl(scf.IfElse)
    def if_else(
        self,
        interp_: _StimFromSquinValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.IfElse,
    ):
        if stmt.cond.type == MeasurementResultType:
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "MeasurementResult cannot be used directly as an IfElse condition "
                    "for rewriting to Stim IR. Use a predicate such as is_one instead.",
                ),
            )

        for child in stmt.walk(include_self=False):
            if isinstance(child, scf.IfElse):
                interp_.add_validation_error(
                    stmt,
                    ir.ValidationError(
                        stmt,
                        "Nested IfElse statements are not supported in rewriting to Stim IR.",
                    ),
                )
                break

        if stmt.else_body.blocks and not (
            len(stmt.else_body.blocks[0].stmts) == 1
            and isinstance(stmt.else_body.blocks[0].last_stmt, scf.Yield)
        ):
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "IfElse statements with an else body are not supported in rewriting to Stim IR.",
                ),
            )

        for child in stmt.then_body.walk():
            if isinstance(child, gate.stmts.Gate) and not isinstance(
                child, PauliGateType
            ):
                interp_.add_validation_error(
                    stmt,
                    ir.ValidationError(
                        stmt,
                        f"Only Pauli gates (X, Y, Z) are allowed inside an scf.IfElse "
                        f"'then'-body for rewriting to Stim IR. Found: {type(child).__name__}",
                    ),
                )

    @interp.impl(scf.For)
    def for_loop(
        self,
        interp_: _StimFromSquinValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: scf.For,
    ):
        if not _is_supported_iterable(stmt.iterable):
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "Loops in Stim kernels must use `range(n)` with a positive "
                    "compile-time constant `n`. Multi-arg ranges, runtime counts, "
                    "and other iterables are not supported.",
                ),
            )


@func.dialect.register(key="stim.validate.from_squin")
class _FuncMethods(interp.MethodTable):

    @interp.impl(func.Return)
    def return_stmt(
        self,
        interp_: _StimFromSquinValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: func.Return,
    ):
        if stmt.value.type != types.NoneType:
            interp_.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    f"Kernel must return None for rewriting to Stim IR, "
                    f"but returns {stmt.value.type}.",
                ),
            )


@qubit_stmts.dialect.register(key="stim.validate.from_squin")
class _QubitMethods(interp.MethodTable):

    @interp.impl(qubit_stmts.IsZero)
    def is_zero(
        self,
        interp_: _StimFromSquinValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: qubit_stmts.IsZero,
    ):
        interp_.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                "is_zero predicate is not supported in rewriting to Stim IR. Only the is_one predicate is supported.",
            ),
        )

    @interp.impl(qubit_stmts.IsLost)
    def is_lost(
        self,
        interp_: _StimFromSquinValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: qubit_stmts.IsLost,
    ):
        interp_.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                "is_lost predicate is not supported in rewriting to Stim IR. Only the is_one predicate is supported.",
            ),
        )


class StimFromSquinValidation(ValidationPass):
    def name(self) -> str:
        return "Stim from Squin Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        analysis = _StimFromSquinValidationAnalysis(method.dialects)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
