from kirin import interp
from kirin.analysis import ForwardFrame
from kirin.dialects import scf

from .lattice import May, Top, Must, Bottom, QubitValidation
from .analysis import (
    QubitValidationError,
    PotentialQubitValidationError,
    _NoCloningAnalysis,
)


@scf.dialect.register(key="validate.nocloning")
class Scf(interp.MethodTable):
    @interp.impl(scf.IfElse)
    def if_else(
        self,
        interp_: _NoCloningAnalysis,
        frame: ForwardFrame[QubitValidation],
        stmt: scf.IfElse,
    ):
        try:
            cond_validation = frame.get(stmt.cond)
        except Exception:
            cond_validation = Top()

        errors_before_then = len(interp_._validation_errors)
        with interp_.new_frame(stmt, has_parent_access=True) as then_frame:
            interp_.frame_call_region(then_frame, stmt, stmt.then_body, cond_validation)
            frame.set_values(then_frame.entries.keys(), then_frame.entries.values())
        errors_after_then = len(interp_._validation_errors)

        then_had_errors = errors_after_then > errors_before_then
        then_errors = interp_._validation_errors[errors_before_then:errors_after_then]
        then_state = (
            Must(violations=frozenset(err.args[0] for err in then_errors))
            if then_had_errors
            else Bottom()
        )

        if stmt.else_body:
            errors_before_else = len(interp_._validation_errors)
            with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
                interp_.frame_call_region(
                    else_frame, stmt, stmt.else_body, cond_validation
                )
                frame.set_values(else_frame.entries.keys(), else_frame.entries.values())
            errors_after_else = len(interp_._validation_errors)

            else_had_errors = errors_after_else > errors_before_else
            else_errors = interp_._validation_errors[
                errors_before_else:errors_after_else
            ]
            else_state = (
                Must(violations=frozenset(err.args[0] for err in else_errors))
                if else_had_errors
                else Bottom()
            )

            merged = then_state.join(else_state)

            if isinstance(merged, May):
                interp_._validation_errors = interp_._validation_errors[
                    :errors_before_then
                ]

                for err in then_errors + else_errors:
                    if isinstance(err, QubitValidationError):
                        potential_err = PotentialQubitValidationError(
                            err.node,
                            err.gate_name,
                            (
                                ", when condition is true"
                                if err in then_errors
                                else ", when condition is false"
                            ),
                        )
                        interp_._validation_errors.append(potential_err)
        else:
            merged = then_state.join(Bottom())

            if isinstance(merged, May):
                interp_._validation_errors = interp_._validation_errors[
                    :errors_before_then
                ]

                for err in then_errors:
                    if isinstance(err, QubitValidationError):
                        potential_err = PotentialQubitValidationError(
                            err.node, err.gate_name, ", when condition is true"
                        )
                        interp_._validation_errors.append(potential_err)

        return (merged,)
