from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import op, noise, qubit
from bloqade.squin.rewrite import AddressAttribute
from bloqade.stim.rewrite.util import (
    SQUIN_STIM_OP_MAPPING,
    rewrite_Control,
    rewrite_QubitLoss,
    insert_qubit_idx_from_address,
)


class SquinQubitToStim(RewriteRule):
    """
    NOTE this require address analysis result to be wrapped before using this rule.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case qubit.Apply() | qubit.Broadcast():
                return self.rewrite_Apply_and_Broadcast(node)
            case _:
                return RewriteResult()

    def rewrite_Apply_and_Broadcast(
        self, stmt: qubit.Apply | qubit.Broadcast
    ) -> RewriteResult:
        """
        Rewrite Apply and Broadcast nodes to their stim equivalent statements.
        """

        # this is an SSAValue, need it to be the actual operator
        applied_op = stmt.operator.owner

        if isinstance(applied_op, noise.stmts.QubitLoss):
            return rewrite_QubitLoss(stmt)

        assert isinstance(applied_op, op.stmts.Operator)

        # Handle controlled gates with a separate procedure
        if isinstance(applied_op, op.stmts.Control):
            return rewrite_Control(stmt)

        # check if its adjoint, assume its canonicalized so no nested adjoints.
        is_conj = False
        if isinstance(applied_op, op.stmts.Adjoint):
            # By default the Adjoint has is_unitary = False, so we need to check
            # the inner applied operator to make sure its not just unitary,
            # but something that has an equivalent stim representation with *_DAG format.
            if isinstance(
                applied_op.op.owner, (op.stmts.SqrtX, op.stmts.SqrtY, op.stmts.S)
            ):
                is_conj = True
                applied_op = applied_op.op.owner
            else:
                return RewriteResult()

        stim_1q_op = SQUIN_STIM_OP_MAPPING.get(type(applied_op))
        if stim_1q_op is None:
            return RewriteResult()

        address_attr = stmt.qubits[0].hints.get("address")

        if address_attr is None:
            return RewriteResult()

        assert isinstance(address_attr, AddressAttribute)
        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=stmt
        )

        if qubit_idx_ssas is None:
            return RewriteResult()

        # At this point, we know for certain stim_1q_op must be SQRT_X, SQRT_Y, or S
        # and has the option to set the dagger attribute. If is_conj is false,
        # the rewrite would have terminated early so we know anything else has to be
        # a non 1Q gate operation.
        if is_conj:
            stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas), dagger=is_conj)
        else:
            stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas))
        stmt.replace_by(stim_1q_stmt)

        return RewriteResult(has_done_something=True)
