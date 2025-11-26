from kirin import interp
from kirin.analysis import ForwardFrame
from kirin.dialects import scf

from bloqade.analysis.address import Address

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

        # TODO: check if the condition is constant and fix the branch in that case
        # run both branches
        with interp_.new_frame(stmt, has_parent_access=True) as then_frame:
            # NOTE: reset fidelities before stepping into the then-body
            interp_.reset_fidelities()

            interp_.frame_call_region(
                then_frame,
                stmt,
                stmt.then_body,
                *(interp_.lattice.bottom() for _ in range(len(stmt.args))),
            )
            then_fids = interp_.gate_fidelities
            then_survival = interp_.qubit_survival_fidelities

        with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
            # NOTE: reset again before stepping into else-body
            interp_.reset_fidelities()

            interp_.frame_call_region(
                else_frame,
                stmt,
                stmt.else_body,
                *(interp_.lattice.bottom() for _ in range(len(stmt.args))),
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
