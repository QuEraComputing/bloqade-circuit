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

        errors_before = set(interp_._validation_errors.keys())

        with interp_.new_frame(stmt, has_parent_access=True) as then_frame:
            interp_.frame_call_region(then_frame, stmt, stmt.then_body, cond_validation)
            frame.set_values(then_frame.entries.keys(), then_frame.entries.values())

        then_keys = set(interp_._validation_errors.keys()) - errors_before
        then_errors = interp_.get_validation_errors(keys=then_keys)

        then_state = (
            Must(violations=frozenset(err.args[0] for err in then_errors))
            if then_keys
            else Bottom()
        )

        if stmt.else_body:
            errors_before_else = set(interp_._validation_errors.keys())

            with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
                interp_.frame_call_region(
                    else_frame, stmt, stmt.else_body, cond_validation
                )
                frame.set_values(else_frame.entries.keys(), else_frame.entries.values())

            else_keys = set(interp_._validation_errors.keys()) - errors_before_else
            else_errors = interp_.get_validation_errors(keys=else_keys)

            else_state = (
                Must(violations=frozenset(err.args[0] for err in else_errors))
                if else_keys
                else Bottom()
            )
        else:
            else_state = Bottom()
            else_keys = set()
            else_errors = []
        merged = then_state.join(else_state)
        all_branch_keys = then_keys | else_keys
        for k in all_branch_keys:
            interp_._validation_errors.pop(k, None)

        if isinstance(merged, Must):
            for err in then_errors + else_errors:
                if isinstance(err, QubitValidationError):
                    interp_.add_validation_error(err.node, err)
        elif isinstance(merged, May):
            for err in then_errors:
                if isinstance(err, QubitValidationError):
                    potential_err = PotentialQubitValidationError(
                        err.node, err.gate_name, ", when condition is true"
                    )
                    interp_.add_validation_error(err.node, potential_err)

            for err in else_errors:
                if isinstance(err, QubitValidationError):
                    potential_err = PotentialQubitValidationError(
                        err.node, err.gate_name, ", when condition is false"
                    )
                    interp_.add_validation_error(err.node, potential_err)
        return (merged,)
