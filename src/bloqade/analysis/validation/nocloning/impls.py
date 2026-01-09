from kirin import interp
from kirin.analysis import ForwardFrame
from kirin.dialects import scf

from .lattice import May, Top, Must, Bottom, QubitValidation
from .analysis import _NoCloningAnalysis


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

        with interp_.new_frame(stmt, has_parent_access=True) as then_frame:
            interp_.frame_call_region(then_frame, stmt, stmt.then_body, cond_validation)

        then_state = Bottom()
        for node, val in then_frame.entries.items():
            if isinstance(val, (Must, May)):
                then_state = then_state.join(val)

        else_state = Bottom()
        if stmt.else_body:
            with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
                interp_.frame_call_region(
                    else_frame, stmt, stmt.else_body, cond_validation
                )

            for node, val in else_frame.entries.items():
                if isinstance(val, (Must, May)):
                    else_state = else_state.join(val)

        merged = then_state.join(else_state)

        if isinstance(merged, May):
            then_has = not isinstance(then_state, Bottom)
            else_has = not isinstance(else_state, Bottom)

            if then_has and not else_has:
                new_violations = frozenset(
                    (gate, ", when condition is true") for gate, _ in merged.violations
                )
                merged = May(violations=new_violations)
            elif else_has and not then_has:
                new_violations = frozenset(
                    (gate, ", when condition is false") for gate, _ in merged.violations
                )
                merged = May(violations=new_violations)

        return (merged,)
