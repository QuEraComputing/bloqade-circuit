from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import qubit, clifford
from bloqade.squin.rewrite import AddressAttribute
from bloqade.stim.dialects import gate as stim_gate, collapse as stim_collapse
from bloqade.stim.rewrite.util import (
    insert_qubit_idx_from_address,
)


class SquinQubitToStim(RewriteRule):
    """
    NOTE this require address analysis result to be wrapped before using this rule.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            # not supported by Stim
            case clifford.stmts.T() | clifford.stmts.RotationGate():
                return RewriteResult()
            # If you've reached this point all gates have stim equivalents
            case qubit.Reset():
                return self.rewrite_Reset(node)
            case clifford.stmts.SingleQubitGate():
                return self.rewrite_SingleQubitGate(node)
            case clifford.stmts.ControlledGate():
                return self.rewrite_ControlledGate(node)
            case _:
                return RewriteResult()

    def rewrite_Reset(self, stmt: qubit.Reset) -> RewriteResult:

        qubit_addr_attr = stmt.qubits.hints.get("address", None)
        assert isinstance(qubit_addr_attr, AddressAttribute)

        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=qubit_addr_attr, stmt_to_insert_before=stmt
        )

        if qubit_idx_ssas is None:
            return RewriteResult()

        stim_stmt = stim_collapse.RZ(targets=tuple(qubit_idx_ssas))
        stmt.replace_by(stim_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_SingleQubitGate(
        self, stmt: clifford.stmts.SingleQubitGate
    ) -> RewriteResult:
        """
        Rewrite single qubit gate nodes to their stim equivalent statements.
        Address Analysis should have been run along with Wrap Analysis before this rewrite is applied.
        """

        qubit_addr_attr = stmt.qubits.hints.get("address", None)
        assert isinstance(qubit_addr_attr, AddressAttribute)

        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=qubit_addr_attr, stmt_to_insert_before=stmt
        )

        if qubit_idx_ssas is None:
            return RewriteResult()

        # Get the name of the inputted stmt and see if there is an
        # equivalently named statement in stim,
        # then create an instance of that stim statement
        stmt_name = type(stmt).__name__
        stim_stmt_cls = getattr(stim_gate.stmts, stmt_name, None)
        if stim_stmt_cls is None:
            return RewriteResult()
        stim_stmt = stim_stmt_cls(targets=tuple(qubit_idx_ssas))
        stmt.replace_by(stim_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_ControlledGate(
        self, stmt: clifford.stmts.ControlledGate
    ) -> RewriteResult:
        """
        Rewrite controlled gate nodes to their stim equivalent statements.
        Address Analysis should have been run along with Wrap Analysis before this rewrite is applied.
        """

        controls_addr_attr = stmt.controls.hints.get("address", None)
        targets_addr_attr = stmt.targets.hints.get("address", None)

        assert isinstance(controls_addr_attr, AddressAttribute)
        assert isinstance(targets_addr_attr, AddressAttribute)

        controls_idx_ssas = insert_qubit_idx_from_address(
            address=controls_addr_attr, stmt_to_insert_before=stmt
        )
        targets_idx_ssas = insert_qubit_idx_from_address(
            address=targets_addr_attr, stmt_to_insert_before=stmt
        )

        if controls_idx_ssas is None or targets_idx_ssas is None:
            return RewriteResult()

        # Get the name of the inputted stmt and see if there is an
        # equivalently named statement in stim,
        # then create an instance of that stim statement
        stmt_name = type(stmt).__name__
        stim_stmt_cls = getattr(stim_gate.stmts, stmt_name, None)
        if stim_stmt_cls is None:
            return RewriteResult()

        stim_stmt = stim_stmt_cls(
            targets=tuple(targets_idx_ssas), controls=tuple(controls_idx_ssas)
        )
        stmt.replace_by(stim_stmt)

        return RewriteResult(has_done_something=True)
