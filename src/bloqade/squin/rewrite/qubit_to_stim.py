from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import stim
from bloqade.squin import op, qubit
from bloqade.squin.rewrite.wrap_analysis import AddressAttribute
from bloqade.squin.rewrite.stim_rewrite_util import (
    SQUIN_STIM_GATE_MAPPING,
    rewrite_Control,
    are_sites_compatible,
    insert_qubit_idx_from_address,
)


class SquinQubitToStim(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case qubit.Apply() | qubit.Broadcast():
                return self.rewrite_Apply_and_Broadcast(node)
            case qubit.Reset():
                return self.rewrite_Reset(node)
            case _:
                return RewriteResult()

    def rewrite_Apply_and_Broadcast(
        self, stmt: qubit.Apply | qubit.Broadcast
    ) -> RewriteResult:
        """
        Rewrite Apply and Broadcast nodes to their stim equivalent statements.
        """
        # get rid of are_sites_compatible, assume program is properly structured
        if not are_sites_compatible(stmt):
            return RewriteResult()

        # this is an SSAValue, need it to be the actual operator
        applied_op = stmt.operator.owner
        assert isinstance(applied_op, op.stmts.Operator)

        if isinstance(applied_op, op.stmts.Control):
            return rewrite_Control(stmt)

        # need to handle Control through separate means
        # but we can handle X, Y, Z, H, and S here just fine
        stim_1q_op = SQUIN_STIM_GATE_MAPPING.get(type(applied_op))
        if stim_1q_op is None:
            return RewriteResult()

        address_attr = stmt.qubits.hints.get("address")
        if address_attr is None:
            return RewriteResult()

        assert isinstance(address_attr, AddressAttribute)
        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=stmt
        )

        if qubit_idx_ssas is None:
            return RewriteResult()

        stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas))
        stmt.replace_by(stim_1q_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_Reset(self, reset_stmt: qubit.Reset) -> RewriteResult:
        qubit_ilist_ssa = reset_stmt.qubits
        # qubits are in an ilist which makes up an AddressTuple
        address_attr = qubit_ilist_ssa.hints.get("address")
        if address_attr is None:
            return RewriteResult()

        assert isinstance(address_attr, AddressAttribute)
        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=reset_stmt
        )

        if qubit_idx_ssas is None:
            return RewriteResult()

        stim_rz_stmt = stim.collapse.stmts.RZ(targets=qubit_idx_ssas)
        reset_stmt.replace_by(stim_rz_stmt)

        return RewriteResult(has_done_something=True)


# put rewrites for measure statements in separate rule, then just have to dispatch
