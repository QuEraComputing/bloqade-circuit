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

        # NOTE: reset one last time to the state before
        interp_.reset_fidelities()

        # TODO: maybe combine this with interp.extend_fidelities?
        # NOTE: make sure they are all of the same length
        n = interp_.qubit_count
        current_gate_fidelities.extend(
            [[1.0, 1.0] for _ in range(n - len(current_gate_fidelities))]
        )
        current_survival_fidelities.extend(
            [[1.0, 1.0] for _ in range(n - len(current_survival_fidelities))]
        )
        then_fids.extend([[1.0, 1.0] for _ in range(n - len(then_fids))])
        else_fids.extend([[1.0, 1.0] for _ in range(n - len(else_fids))])

        # NOTE: now we update min / max accordingly
        for i, (current_fid, then_fid, else_fid) in enumerate(
            zip(current_gate_fidelities, then_fids, else_fids)
        ):
            interp_.gate_fidelities[i][0] = current_fid[0] * min(
                then_fid[0], else_fid[0]
            )
            interp_.gate_fidelities[i][1] = current_fid[1] * max(
                then_fid[1], else_fid[1]
            )

        for i, (current_surv, then_surv, else_surv) in enumerate(
            zip(current_survival_fidelities, then_survival, else_survival)
        ):
            interp_.qubit_survival_fidelities[i][0] = current_surv[0] * min(
                then_surv[0], else_surv[0]
            )
            interp_.qubit_survival_fidelities[i][1] = current_surv[1] * max(
                then_surv[1], else_surv[1]
            )
