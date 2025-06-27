from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import op, qubit
from bloqade.squin.rewrite import AddressAttribute
from bloqade.stim.dialects import gate
from bloqade.stim.rewrite.util import (
    SQUIN_STIM_GATE_MAPPING,
    rewrite_Control,
    insert_qubit_idx_from_address,
)


class SquinQubitToStim(RewriteRule):

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
        assert isinstance(applied_op, op.stmts.Operator)

        if isinstance(applied_op, op.stmts.Control):
            return rewrite_Control(stmt)

        # check if its adjoint, assume its canonicalized so no nested adjoints.
        is_conj = False
        if isinstance(applied_op, op.stmts.Adjoint):
            if not applied_op.is_unitary:
                return RewriteResult()

            is_conj = True
            applied_op = applied_op.op.owner

        # need to handle Control through separate means
        # but we can handle X, Y, Z, H, and S here just fine
        stim_1q_op = SQUIN_STIM_GATE_MAPPING.get(type(applied_op))
        if stim_1q_op is None:
            return RewriteResult()

        address_attr = stmt.qubits.hints.get("address")

        if address_attr is None:
            return RewriteResult()

        # sometimes you can get a whole AddressReg...
        assert isinstance(address_attr, AddressAttribute)
        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address_attr, stmt_to_insert_before=stmt
        )

        if qubit_idx_ssas is None:
            return RewriteResult()

        if isinstance(stim_1q_op, gate.stmts.Gate):
            stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas), dagger=is_conj)
        else:
            stim_1q_stmt = stim_1q_op(targets=tuple(qubit_idx_ssas))
        stmt.replace_by(stim_1q_stmt)

        return RewriteResult(has_done_something=True)


# put rewrites for measure statements in separate rule, then just have to dispatch
