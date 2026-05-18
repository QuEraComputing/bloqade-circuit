from kirin import interp
from kirin.analysis import ForwardFrame, const
from kirin.dialects import scf

from bloqade.analysis.address import Address, ConstResult

from .analysis import FidelityAnalysis


@scf.dialect.register(key="circuit.fidelity")
class __ScfMethods(interp.MethodTable):
    @interp.impl(scf.IfElse)
    def if_else(
        self, interp_: FidelityAnalysis, frame: ForwardFrame[Address], stmt: scf.IfElse
    ):

        # NOTE: store a copy of the fidelities
        current_gate_fidelities = interp_.gate_fidelities
        current_survival_fidelities = interp_.qubit_survival_fidelities

        address_cond = frame.get(stmt.cond)

        # NOTE: if the condition is known at compile time, run specific branch
        if isinstance(address_cond, ConstResult) and isinstance(
            const_cond := address_cond.result, const.Value
        ):
            body = stmt.then_body if const_cond.data else stmt.else_body
            with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
                ret = interp_.frame_call_region(body_frame, stmt, body, address_cond)
                return ret

        # NOTE: runtime condition, evaluate both
        with interp_.new_frame(stmt, has_parent_access=True) as then_frame:
            # NOTE: reset fidelities before stepping into the then-body
            interp_.reset_fidelities()

            then_results = interp_.frame_call_region(
                then_frame,
                stmt,
                stmt.then_body,
                address_cond,
            )
            then_fids = interp_.gate_fidelities
            then_survival = interp_.qubit_survival_fidelities

        with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
            # NOTE: reset again before stepping into else-body
            interp_.reset_fidelities()

            else_results = interp_.frame_call_region(
                else_frame,
                stmt,
                stmt.else_body,
                address_cond,
            )

            else_fids = interp_.gate_fidelities
            else_survival = interp_.qubit_survival_fidelities

        # NOTE: reset one last time
        interp_.reset_fidelities()

        # NOTE: now update min / max pairs accordingly
        interp_.update_branched_fidelities(
            interp_.gate_fidelities, current_gate_fidelities, then_fids, else_fids
        )
        interp_.update_branched_fidelities(
            interp_.qubit_survival_fidelities,
            current_survival_fidelities,
            then_survival,
            else_survival,
        )

        # TODO: pick the non-return value
        if isinstance(then_results, interp.ReturnValue) and isinstance(
            else_results, interp.ReturnValue
        ):
            return interp.ReturnValue(then_results.value.join(else_results.value))
        elif isinstance(then_results, interp.ReturnValue):
            ret = else_results
        elif isinstance(else_results, interp.ReturnValue):
            ret = then_results
        else:
            ret = interp_.join_results(then_results, else_results)

        return ret
