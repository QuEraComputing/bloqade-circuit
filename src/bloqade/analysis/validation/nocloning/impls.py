from kirin import interp
from kirin.analysis import ForwardFrame
from kirin.dialects import scf

from .lattice import QubitValidation
from .analysis import NoCloningValidation


@scf.dialect.register(key="validate.nocloning")
class Scf(interp.MethodTable):
    @interp.impl(scf.IfElse)
    def if_else(
        self,
        interp_: NoCloningValidation,
        frame: ForwardFrame[QubitValidation],
        stmt: scf.IfElse,
    ):
        cond_validation = frame.get(stmt.cond)

        then_results = interp_.run_callable_region(
            frame, stmt, stmt.then_body, (cond_validation,)
        )

        if stmt.else_body:
            else_results = interp_.run_callable_region(
                frame, stmt, stmt.else_body, (cond_validation,)
            )

            merged = tuple(then_results.join(else_results) for _ in stmt.results)
        else:
            merged = tuple(then_results for _ in stmt.results)

        return merged if merged else (QubitValidation.bottom(),)
