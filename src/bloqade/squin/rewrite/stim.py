from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import stim
from bloqade.squin import op, wire, qubit
from bloqade.squin.rewrite.stim_util import (
    get_stim_1q_gate,
    verify_num_sites,
    insert_qubit_idx_from_address,
    insert_qubit_idx_from_wire_ssa,
)
from bloqade.squin.rewrite.wrap_analysis import AddressAttribute


@dataclass
class _SquinToStim(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case wire.Apply() | qubit.Apply() | wire.Broadcast() | qubit.Broadcast():
                verify_num_sites(node)
                return self.rewrite_Apply_and_Broadcast(node)
            case wire.Wrap():
                return self.rewrite_Wrap(node)
            case wire.Measure() | qubit.MeasureQubit() | qubit.MeasureQubitList():
                return self.rewrite_Measure(node)
            case wire.Reset() | qubit.Reset():
                return self.rewrite_Reset(node)
            case wire.MeasureAndReset() | qubit.MeasureAndReset():
                return self.rewrite_MeasureAndReset(node)
            case _:
                return RewriteResult()

    def rewrite_Wrap(self, wrap_stmt: wire.Wrap) -> RewriteResult:

        # get the wire going into the statement
        wire_ssa = wrap_stmt.wire
        # remove the wrap statement altogether, then the wire that went into it
        wrap_stmt.delete()
        wire_ssa.delete()

        # do NOT want to delete the qubit SSA! Leave that alone!
        return RewriteResult(has_done_something=True)

    def rewrite_Apply_and_Broadcast(
        self, apply_stmt: qubit.Apply | wire.Apply | qubit.Broadcast | wire.Broadcast
    ) -> RewriteResult:
        # this is an SSAValue, need it to be the actual operator
        applied_op = apply_stmt.operator.owner
        assert isinstance(applied_op, op.stmts.Operator)

        if isinstance(applied_op, op.stmts.Control):
            return self.rewrite_Control(apply_stmt)

        # need to handle Control through separate means
        # but we can handle X, Y, Z, H, and S here just fine
        stim_1q_op = get_stim_1q_gate(applied_op)

        if isinstance(apply_stmt, (qubit.Apply, qubit.Broadcast)):
            address_attr = apply_stmt.qubits.hints.get("address")
            assert isinstance(address_attr, AddressAttribute)
            qubit_idx_ssas = insert_qubit_idx_from_address(
                address=address_attr, stmt_to_insert_before=apply_stmt
            )
        elif isinstance(apply_stmt, (wire.Apply, wire.Broadcast)):
            qubit_idx_ssas = insert_qubit_idx_from_wire_ssa(
                wire_ssas=apply_stmt.inputs, stmt_to_insert_before=apply_stmt
            )
        else:
            raise TypeError(
                "Unsupported statement detected, only Apply and Broadcast statements are permitted"
            )

        stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas))
        stim_1q_stmt.insert_before(apply_stmt)

        # Could I safely delete the apply statements?
        # If it's a qubit.Apply or qubit.Broadcast, yes, because it doesn't return anything
        # If it's a wire.Apply or wire.Broadcast, no, because the `results` of that Apply/Broadcast get used later on
        if isinstance(apply_stmt, (qubit.Apply, qubit.Broadcast)):
            apply_stmt.delete()

        return RewriteResult(has_done_something=True)

    def rewrite_Control(
        self,
        stmt_with_ctrl: qubit.Apply | wire.Apply | qubit.Broadcast | wire.Broadcast,
    ) -> RewriteResult:
        """
        Handle control gates for Apply and Broadcast statements.
        """
        ctrl_op = stmt_with_ctrl.operator.owner
        assert isinstance(ctrl_op, op.stmts.Control)

        ctrl_op_target_gate = ctrl_op.op.owner
        assert isinstance(ctrl_op_target_gate, op.stmts.Operator)

        qubit_idx_ssas = self.insert_qubit_idx_after_apply(stmt=stmt_with_ctrl)

        # Separate control and target qubits
        target_qubits = []
        ctrl_qubits = []
        for i in range(len(qubit_idx_ssas)):
            if (i % 2) == 0:
                ctrl_qubits.append(qubit_idx_ssas[i])
            else:
                target_qubits.append(qubit_idx_ssas[i])

        target_qubits = tuple(target_qubits)
        ctrl_qubits = tuple(ctrl_qubits)

        # Handle supported gates
        match ctrl_op_target_gate:
            case op.stmts.X():
                stim_stmt = stim.CX(controls=ctrl_qubits, targets=target_qubits)
            case op.stmts.Y():
                stim_stmt = stim.CY(controls=ctrl_qubits, targets=target_qubits)
            case op.stmts.Z():
                stim_stmt = stim.CZ(controls=ctrl_qubits, targets=target_qubits)
            case _:
                raise NotImplementedError(
                    "Control gates beyond CX, CY, and CZ are not supported"
                )

        stim_stmt.insert_before(stmt_with_ctrl)

        # Delete the original statement if it's a qubit.Apply or qubit.Broadcast
        if isinstance(stmt_with_ctrl, (qubit.Apply, qubit.Broadcast)):
            stmt_with_ctrl.delete()

        return RewriteResult(has_done_something=True)

    def insert_qubit_idx_after_apply(
        self, stmt: wire.Apply | qubit.Apply | wire.Broadcast | qubit.Broadcast
    ) -> tuple[ir.SSAValue, ...]:
        """
        Extract qubit indices from Apply or Broadcast statements.
        """
        if isinstance(stmt, (qubit.Apply, qubit.Broadcast)):
            qubits = stmt.qubits
            address_attribute: AddressAttribute = qubits.hints.get("address")
            return insert_qubit_idx_from_address(
                address=address_attribute, stmt_to_insert_before=stmt
            )
        elif isinstance(stmt, (wire.Apply, wire.Broadcast)):
            wire_ssas = stmt.inputs
            return insert_qubit_idx_from_wire_ssa(
                wire_ssas=wire_ssas, stmt_to_insert_before=stmt
            )
        else:
            raise TypeError(
                "Unsupported statement detected, only Apply and Broadcast statements are supported by this method"
            )

    # qubit.Measure no longer exists, need to handle
    # qubit.MeasureQubit and MeasureQubitList
    def rewrite_Measure(
        self, measure_stmt: wire.Measure | qubit.MeasureQubit | qubit.MeasureQubitList
    ) -> RewriteResult:

        match measure_stmt:
            case qubit.MeasureQubit():
                qubit_ilist_ssa = measure_stmt.qubit
                address_attr = qubit_ilist_ssa.hints.get("address")
                assert isinstance(address_attr, AddressAttribute)
            case qubit.MeasureQubitList():
                qubit_ssa = measure_stmt.qubits
                address_attr = qubit_ssa.hints.get("address")
                assert isinstance(address_attr, AddressAttribute)
            case wire.Measure():
                wire_ssa = measure_stmt.wire
                address_attr = wire_ssa.hints.get("address")
                assert isinstance(address_attr, AddressAttribute)
            case _:
                raise TypeError(
                    "Unsupported Statement, only qubit.MeasureQubit, qubit.MeasureQubitList, and wire.Measure are supported"
                )

        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=measure_stmt
        )

        prob_noise_stmt = py.constant.Constant(0.0)
        stim_measure_stmt = stim.collapse.MZ(
            p=prob_noise_stmt.result,
            targets=qubit_idx_ssas,
        )
        prob_noise_stmt.insert_before(measure_stmt)
        stim_measure_stmt.insert_before(measure_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_Reset(self, reset_stmt: qubit.Reset | wire.Reset) -> RewriteResult:
        """
        qubit.Reset(ilist of qubits) -> nothing
        # safe to delete the statement afterwards, no depending results
        # DCE could probably do this automatically?

        wire.Reset(single wire) -> new wire
        # DO NOT DELETE

        # assume RZ, but could extend to RY and RX later
        Stim RZ(targets = tuple[int of SSAVals])
        """

        if isinstance(reset_stmt, qubit.Reset):
            qubit_ilist_ssa = reset_stmt.qubits
            # qubits are in an ilist which makes up an AddressTuple
            address_attr = qubit_ilist_ssa.hints.get("address")
            assert isinstance(address_attr, AddressAttribute)
            qubit_idx_ssas = insert_qubit_idx_from_address(
                address=address_attr, stmt_to_insert_before=reset_stmt
            )
        elif isinstance(reset_stmt, wire.Reset):
            address_attr = reset_stmt.wire.hints.get("address")
            assert isinstance(address_attr, AddressAttribute)
            qubit_idx_ssas = insert_qubit_idx_from_address(
                address=address_attr, stmt_to_insert_before=reset_stmt
            )
        else:
            raise TypeError(
                "unsupported statement, only qubit.Reset and wire.Reset are supported"
            )

        stim_rz_stmt = stim.collapse.stmts.RZ(targets=qubit_idx_ssas)
        stim_rz_stmt.insert_before(reset_stmt)
        reset_stmt.delete()

        return RewriteResult(has_done_something=True)

    def rewrite_MeasureAndReset(
        self, meas_and_reset_stmt: qubit.MeasureAndReset | wire.MeasureAndReset
    ):
        """
        qubit.MeasureAndReset(qubits) -> result
        Could be translated (roughly equivalent) to

        stim.MZ(tuple[SSAvals for ints])
        stim.RZ(tuple[SSAvals for ints])

        """

        if isinstance(meas_and_reset_stmt, qubit.MeasureAndReset):

            address_attr = meas_and_reset_stmt.qubits.hints.get("address")
            assert isinstance(address_attr, AddressAttribute)
            qubit_idx_ssas = insert_qubit_idx_from_address(
                address=address_attr, stmt_to_insert_before=meas_and_reset_stmt
            )

        elif isinstance(meas_and_reset_stmt, wire.MeasureAndReset):
            address_attr = meas_and_reset_stmt.wire.hints.get("address")
            assert isinstance(address_attr, AddressAttribute)
            qubit_idx_ssas = insert_qubit_idx_from_address(
                address_attr, stmt_to_insert_before=meas_and_reset_stmt
            )

        else:
            raise TypeError(
                "Unsupported statement detected, only qubit.MeasureAndReset and wire.MeasureAndReset are supported"
            )

        error_p_stmt = py.Constant(0.0)
        stim_mz_stmt = stim.collapse.MZ(targets=qubit_idx_ssas, p=error_p_stmt.result)
        stim_rz_stmt = stim.collapse.RZ(
            targets=qubit_idx_ssas,
        )
        error_p_stmt.insert_before(meas_and_reset_stmt)
        stim_mz_stmt.insert_before(meas_and_reset_stmt)
        stim_rz_stmt.insert_before(meas_and_reset_stmt)

        return RewriteResult(has_done_something=True)
