from kirin import interp as _interp
from kirin.analysis import const
from kirin.dialects import scf, func

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
        return (
            Error(stmt, "if statements are not supported in logical Gemini programs!"),
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

        return (
            (
                Error(
                    stmt,
                    "Non-constant iterable in for loop is not supported in Gemini logical programs!",
                )
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
        return (
            Error(
                stmt,
                "Function invocations not supported in logical Gemini program!",
                help="Make sure to decorate your function with `@logical(inline = True)` or `@logical(aggressive_unroll = True)` to inline function calls",
            ),
        )
