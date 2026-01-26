from kirin import ir, interp as _interp
from kirin.analysis import ForwardFrame, const
from kirin.dialects import scf, func

from bloqade.squin import gate

from .analysis import _GeminiLogicalValidationAnalysis


@scf.dialect.register(key="gemini.validate.logical")
class __ScfGeminiLogicalValidation(_interp.MethodTable):

    @_interp.impl(scf.IfElse)
    def if_else(
        self,
        interp: _GeminiLogicalValidationAnalysis,
        frame: ForwardFrame,
        stmt: scf.IfElse,
    ):
        interp.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt, "If statements are not supported in logical Gemini programs!"
            ),
        )
        return (interp.lattice.bottom(),)

    @_interp.impl(scf.For)
    def for_loop(
        self,
        interp: _GeminiLogicalValidationAnalysis,
        frame: ForwardFrame,
        stmt: scf.For,
    ):
        if not isinstance(stmt.iterable.hints.get("const"), const.Value):

            interp.add_validation_error(
                stmt,
                ir.ValidationError(
                    stmt,
                    "Non-constant iterable in for loop is not supported in Gemini logical programs!",
                ),
            )

        return (interp.lattice.bottom(),)


@func.dialect.register(key="gemini.validate.logical")
class __FuncGeminiLogicalValidation(_interp.MethodTable):
    @_interp.impl(func.Invoke)
    def invoke(
        self,
        interp: _GeminiLogicalValidationAnalysis,
        frame: ForwardFrame,
        stmt: func.Invoke,
    ):
        interp.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                "Function invocations not supported in logical Gemini program!",
                help="Make sure to decorate your function with `@logical(inline = True)` or `@logical(aggressive_unroll = True)` to inline function calls",
            ),
        )

        return tuple(interp.lattice.bottom() for _ in stmt.results)


@gate.dialect.register(key="gemini.validate.logical")
class __GateGeminiLogicalValidation(_interp.MethodTable):

    @_interp.impl(gate.stmts.U3)
    @_interp.impl(gate.stmts.T)
    @_interp.impl(gate.stmts.Rx)
    @_interp.impl(gate.stmts.Ry)
    @_interp.impl(gate.stmts.Rz)
    def non_clifford(
        self,
        interp: _GeminiLogicalValidationAnalysis,
        frame: ForwardFrame,
        stmt: gate.stmts.SingleQubitGate | gate.stmts.RotationGate,
    ):
        if interp.check_first_gate(stmt.qubits):
            return ()

        interp.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                f"Non-clifford gate {stmt.name} can only be used for initial state preparation, i.e. as the first gate!",
            ),
        )
        return ()

    @_interp.impl(gate.stmts.X)
    @_interp.impl(gate.stmts.Y)
    @_interp.impl(gate.stmts.SqrtX)
    @_interp.impl(gate.stmts.SqrtY)
    @_interp.impl(gate.stmts.Z)
    @_interp.impl(gate.stmts.H)
    @_interp.impl(gate.stmts.S)
    def clifford(
        self,
        interp: _GeminiLogicalValidationAnalysis,
        frame: ForwardFrame,
        stmt: gate.stmts.SingleQubitGate,
    ):
        # NOTE: ignore result, but make sure the first gate flag is set to False
        interp.check_first_gate(stmt.qubits)

        return ()

    @_interp.impl(gate.stmts.CX)
    @_interp.impl(gate.stmts.CY)
    @_interp.impl(gate.stmts.CZ)
    def controlled_gate(
        self,
        interp: _GeminiLogicalValidationAnalysis,
        frame: ForwardFrame,
        stmt: gate.stmts.ControlledGate,
    ):
        interp.check_first_gate(stmt.controls)
        interp.check_first_gate(stmt.targets)
        return ()
