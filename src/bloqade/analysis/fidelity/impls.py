from kirin import interp
from kirin.dialects import scf, func

from .analysis import FidelityFrame, FidelityAnalysis


@scf.dialect.register(key="circuit.fidelity")
class __ScfMethods(interp.MethodTable):
    @interp.impl(scf.IfElse)
    def if_else(
        self, interp_: FidelityAnalysis, frame: FidelityFrame, stmt: scf.IfElse
    ):
        # TODO: check if the condition is constant and fix the branch in that case
        # run both branches
        with interp_.new_frame(stmt, has_parent_access=True) as then_frame:
            interp_.frame_call_region(
                then_frame,
                stmt,
                stmt.then_body,
            )
            then_fids = then_frame.gate_fidelities

        with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
            interp_.frame_call_region(
                else_frame,
                stmt,
                stmt.else_body,
            )

            else_fids = else_frame.gate_fidelities

        assert (n_qubits := interp_.n_qubits) is not None
        for i in range(n_qubits):
            min_fid = min(then_fids[i][0], else_fids[i][0])
            max_fid = max(then_fids[i][1], else_fids[i][1])
            frame.gate_fidelities[i][0] *= min_fid
            frame.gate_fidelities[i][1] *= max_fid


@func.dialect.register(key="circuit.fidelity")
class __FuncMethods(interp.MethodTable):
    @interp.impl(func.Invoke)
    def invoke_(
        self, interp_: FidelityAnalysis, frame: FidelityFrame, stmt: func.Invoke
    ):
        parent_stmt = frame.parent_stmt or stmt

        addr_frame, _ = interp_.addr_analysis.call(
            stmt.callee,
            interp_.addr_analysis.method_self(stmt.callee),
            *interp_.get_addresses(parent_stmt, stmt.inputs),
        )
        interp_.store_addresses(stmt, addr_frame.entries)

        with interp_.new_frame(stmt.callee.code, has_parent_access=True) as body_frame:
            for arg, input in zip(
                stmt.callee.callable_region.blocks[0].args[
                    1:
                ],  # NOTE: skip method_self
                stmt.inputs,
            ):
                addr = interp_.get_address(parent_stmt, input)
                interp_.store_addresses(parent_stmt, {arg: addr})

            body_frame.parent_stmt = stmt

            ret = interp_.frame_call(
                body_frame,
                stmt.callee.code,
                interp_.method_self(stmt.callee),
                *frame.get_values(stmt.inputs),
            )

        for i, (fid0, fid1) in enumerate(body_frame.gate_fidelities):
            frame.gate_fidelities[i][0] *= fid0
            frame.gate_fidelities[i][1] *= fid1

        return (ret,)
