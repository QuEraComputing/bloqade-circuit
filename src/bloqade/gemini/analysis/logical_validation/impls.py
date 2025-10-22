from kirin import ir, interp as _interp
from kirin.analysis import const
from kirin.dialects import scf, func

from bloqade.squin import gate
from bloqade.validation.analysis import ValidationFrame
from bloqade.validation.analysis.lattice import Error

from .analysis import GeminiLogicalValidationAnalysis


@scf.dialect.register(key="gemini.validate.logical")
class __ScfGeminiLogicalValidation(_interp.MethodTable):

    @_interp.impl(scf.IfElse)
    def if_else(
        self,
        interp: GeminiLogicalValidationAnalysis,
        frame: ValidationFrame,
        stmt: scf.IfElse,
    ):
        frame.errors.append(
            ir.ValidationError(
                stmt, "If statements are not supported in logical Gemini programs!"
            )
        )
        return (
            Error(
                message="If statements are not supported in logical Gemini programs!"
            ),
        )

    @_interp.impl(scf.For)
    def for_loop(
        self,
        interp: GeminiLogicalValidationAnalysis,
        frame: ValidationFrame,
        stmt: scf.For,
    ):
        if isinstance(stmt.iterable.hints.get("const"), const.Value):
            return (interp.lattice.top(),)

        frame.errors.append(
            ir.ValidationError(
                stmt,
                "Non-constant iterable in for loop is not supported in Gemini logical programs!",
            )
        )

        return (
            Error(
                message="Non-constant iterable in for loop is not supported in Gemini logical programs!"
            ),
        )


@func.dialect.register(key="gemini.validate.logical")
class __FuncGeminiLogicalValidation(_interp.MethodTable):
    @_interp.impl(func.Invoke)
    def invoke(
        self,
        interp: GeminiLogicalValidationAnalysis,
        frame: ValidationFrame,
        stmt: func.Invoke,
    ):
        frame.errors.append(
            ir.ValidationError(
                stmt,
                "Function invocations not supported in logical Gemini program!",
                help="Make sure to decorate your function with `@logical(inline = True)` or `@logical(aggressive_unroll = True)` to inline function calls",
            )
        )

        return tuple(
            Error(
                message="Function invocations not supported in logical Gemini program!"
            )
            for _ in stmt.results
        )


@gate.dialect.register(key="gemini.validate.logical")
class __GateGeminiLogicalValidation(_interp.MethodTable):
    @_interp.impl(gate.stmts.U3)
    def u3(
        self,
        interp: GeminiLogicalValidationAnalysis,
        frame: ValidationFrame,
        stmt: gate.stmts.U3,
    ):
        if interp.first_gate:
            interp.first_gate = False
            return ()

        frame.errors.append(
            ir.ValidationError(
                stmt,
                "U3 gate can only be used for initial state preparation, i.e. as the first gate!",
            )
        )
        return ()
