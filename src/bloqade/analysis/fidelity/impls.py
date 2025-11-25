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
                *(interp_.lattice.bottom() for _ in range(len(stmt.args))),
            )
            then_fids = then_frame.gate_fidelities
            then_survival = then_frame.qubit_survival_fidelities

        with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
            interp_.frame_call_region(
                else_frame,
                stmt,
                stmt.else_body,
                *(interp_.lattice.bottom() for _ in range(len(stmt.args))),
            )

            else_fids = else_frame.gate_fidelities
            else_survival = else_frame.qubit_survival_fidelities

        assert (n_qubits := interp_.n_qubits) is not None
        for i in range(n_qubits):
            min_fid = min(then_fids[i][0], else_fids[i][0])
            max_fid = max(then_fids[i][1], else_fids[i][1])
            frame.gate_fidelities[i][0] *= min_fid
            frame.gate_fidelities[i][1] *= max_fid

            min_survival = min(then_survival[i][0], else_survival[i][0])
            max_survival = max(then_survival[i][1], else_survival[i][1])
            frame.qubit_survival_fidelities[i][0] *= min_survival
            frame.qubit_survival_fidelities[i][1] *= max_survival

    # TODO: re-use address analysis?
    @interp.impl(scf.For)
    def for_loop(self, interp_: FidelityAnalysis, frame: FidelityFrame, stmt: scf.For):
        loop_vars_addr = interp_.get_addresses(frame, stmt, stmt.initializers)
        loop_vars = tuple(interp_.lattice.bottom() for _ in range(len(stmt.results)))

        iter_type, iterable = interp_.addr_analysis.unpack_iterable(interp_.get_address(frame, stmt, stmt.iterable))

        if iter_type is None:
            return interp_.eval_fallback(frame, stmt)

        for value in iterable:
            with interp_.addr_analysis.new_frame(stmt) as body_addr_frame:
                loop_vars_addr = interp_.addr_analysis.frame_call_region(
                    body_addr_frame, stmt, stmt.body, value, *loop_vars_addr
                )

            with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
                body_frame.parent_stmt = stmt
                interp_.store_addresses(body_frame, stmt, body_addr_frame.entries)

                for (arg, input) in zip(stmt.args, (stmt.iterable, *stmt.initializers)):
                    # NOTE: assign address of input to blockargument
                    addr = interp_.get_address(frame, stmt, input)
                    interp_.store_addresses(body_frame, stmt, {arg: addr})

                interp_.frame_call_region(
                    body_frame, stmt, stmt.body, interp_.lattice.bottom(), *loop_vars
                )

            if loop_vars_addr is None:
                loop_vars_addr = ()
            elif isinstance(loop_vars_addr, interp.ReturnValue):
                break

        return loop_vars


@func.dialect.register(key="circuit.fidelity")
class __FuncMethods(interp.MethodTable):
    # TODO: re-use address analysis method table
    # and re-use the address lattice so we just get addresses in the frame
    @interp.impl(func.Invoke)
    def invoke_(
        self, interp_: FidelityAnalysis, frame: FidelityFrame, stmt: func.Invoke
    ):
        # NOTE: re-run address analysis on the invoke body so we have the addresses of the values inside the body, not just the return
        addr_frame, _ = interp_.addr_analysis.call(
            stmt.callee,
            interp_.addr_analysis.method_self(stmt.callee),
            *interp_.get_addresses(frame, stmt, stmt.inputs),
        )
        interp_.store_addresses(frame, stmt, addr_frame.entries)

        # TODO:
        # * Store address analysis results for the body on the body_frame
        # * Try to run address analysis in parallel with fidelity analysis (in order!)
        # * Maybe re-use the address analysis lattice

        with interp_.new_frame(stmt.callee.code, has_parent_access=True) as body_frame:
            body_frame.parent_stmt = stmt

            for arg, input in zip(
                stmt.callee.callable_region.blocks[0].args[
                    1:
                ],  # NOTE: skip method_self
                stmt.inputs,
            ):

                # NOTE: assign address of input to blockargument
                addr = interp_.get_address(frame, stmt, input)
                interp_.store_addresses(body_frame, stmt, {arg: addr})

            # NOTE: actually call the invoke to evaluate fidelity
            ret = interp_.frame_call(
                body_frame,
                stmt.callee.code,
                interp_.method_self(stmt.callee),
                *frame.get_values(stmt.inputs),
            )

        for i, (fid0, fid1) in enumerate(body_frame.gate_fidelities):
            frame.gate_fidelities[i][0] *= fid0
            frame.gate_fidelities[i][1] *= fid1

        for i, (fid0, fid1) in enumerate(body_frame.qubit_survival_fidelities):
            frame.qubit_survival_fidelities[i][0] *= fid0
            frame.qubit_survival_fidelities[i][1] *= fid1

        return (ret,)
