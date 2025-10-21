from kirin import interp as _interp
from kirin.analysis import ForwardFrame, const
from kirin.dialects import scf

from bloqade.squin import qubit
from bloqade.validation.analysis.lattice import Error

from .analysis import GeminiLogicalValidationAnalysis


@qubit.dialect.register(key="gemini.validate.logical")
class __QubitGeminiLogicalValidation(_interp.MethodTable):

    @_interp.impl(qubit.New)
    def new(
        self,
        interp: GeminiLogicalValidationAnalysis,
        frame: ForwardFrame,
        stmt: qubit.New,
    ):
        # TODO: this is actually tricky, since qalloc calls qubit.new multiple times and we have to make sure qalloc is only called once
        # but it can technically contain many qubit.new calls
        # if interp.has_allocated_qubits:
        #     raise ir.ValidationError(
        #         stmt, "Can only allocate qubits once in a logical Gemini program!"
        #     )

        # interp.has_allocated_qubits = True

        pass


@scf.dialect.register(key="gemini.validate.logical")
class __ScfGeminiLogicalValidation(_interp.MethodTable):

    @_interp.impl(scf.IfElse)
    def if_else(
        self,
        interp: GeminiLogicalValidationAnalysis,
        frame: ForwardFrame,
        stmt: scf.IfElse,
    ):
        return (
            Error(stmt, "if statements are not supported in logical Gemini programs!"),
        )

    @_interp.impl(scf.For)
    def for_loop(
        self,
        interp: GeminiLogicalValidationAnalysis,
        frame: ForwardFrame,
        stmt: scf.For,
    ):
        if isinstance(stmt.iterable.hints.get("const"), const.Value):
            return (interp.lattice.top(),)

        return (
            (
                Error(
                    stmt,
                    "Non-constant iterable in for loop is not supported in Gemini logical programs!",
                ),
            ),
        )
