from dataclasses import dataclass

from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import qubit
from bloqade.squin import gate
from bloqade.stim.dialects import gate as stim_gate, collapse as stim_collapse
from bloqade.analysis.address import Address
from bloqade.stim.rewrite.util import insert_qubit_idx_from_address


@dataclass
class SquinResetToStim(RewriteRule):
    address_analysis: dict[ir.SSAValue, Address]

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, qubit.stmts.Reset):
            return RewriteResult()

        address = self.address_analysis.get(node.qubits)
        if address is None:
            return RewriteResult()

        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address, stmt_to_insert_before=node
        )

        if qubit_idx_ssas is None:
            return RewriteResult()

        stim_stmt = stim_collapse.RZ(targets=tuple(qubit_idx_ssas))
        node.replace_by(stim_stmt)

        return RewriteResult(has_done_something=True)


@dataclass
class SquinGateToStim(RewriteRule):
    address_analysis: dict[ir.SSAValue, Address]

    def _get_address(self, value: ir.SSAValue) -> Address | None:
        return self.address_analysis.get(value)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        match node:
            case gate.stmts.SingleQubitGate():
                return self.rewrite_SingleQubitGate(node)
            case gate.stmts.ControlledGate():
                return self.rewrite_ControlledGate(node)
            case gate.stmts.RotationGate():
                return self.rewrite_RotationGate(node)
            case gate.stmts.U3():
                return self.rewrite_U3Gate(node)
            case _:
                return RewriteResult()

    def rewrite_SingleQubitGate(
        self, stmt: gate.stmts.SingleQubitGate
    ) -> RewriteResult:

        address = self._get_address(stmt.qubits)
        if address is None:
            return RewriteResult()

        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address, stmt_to_insert_before=stmt
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

        if isinstance(stmt, gate.stmts.SingleQubitNonHermitianGate):
            stim_stmt = stim_stmt_cls(
                targets=tuple(qubit_idx_ssas), dagger=stmt.adjoint
            )
        else:
            stim_stmt = stim_stmt_cls(targets=tuple(qubit_idx_ssas))
        stmt.replace_by(stim_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_ControlledGate(self, stmt: gate.stmts.ControlledGate) -> RewriteResult:

        controls_addr = self._get_address(stmt.controls)
        targets_addr = self._get_address(stmt.targets)

        if controls_addr is None or targets_addr is None:
            return RewriteResult()

        controls_idx_ssas = insert_qubit_idx_from_address(
            address=controls_addr, stmt_to_insert_before=stmt
        )
        targets_idx_ssas = insert_qubit_idx_from_address(
            address=targets_addr, stmt_to_insert_before=stmt
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

    def rewrite_RotationGate(self, stmt: gate.stmts.RotationGate) -> RewriteResult:

        address = self._get_address(stmt.qubits)
        if address is None:
            return RewriteResult()

        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address, stmt_to_insert_before=stmt
        )

        if qubit_idx_ssas is None:
            return RewriteResult()

        rotation_gate_map = {
            gate.stmts.Rx: stim_gate.stmts.Rx,
            gate.stmts.Ry: stim_gate.stmts.Ry,
            gate.stmts.Rz: stim_gate.stmts.Rz,
        }

        stim_stmt_cls = rotation_gate_map.get(type(stmt))
        if stim_stmt_cls is None:
            return RewriteResult()

        stim_stmt = stim_stmt_cls(targets=tuple(qubit_idx_ssas), angle=stmt.angle)
        stmt.replace_by(stim_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_U3Gate(self, stmt: gate.stmts.U3) -> RewriteResult:

        address = self._get_address(stmt.qubits)
        if address is None:
            return RewriteResult()

        qubit_idx_ssas = insert_qubit_idx_from_address(
            address=address, stmt_to_insert_before=stmt
        )

        if qubit_idx_ssas is None:
            return RewriteResult()

        stim_stmt = stim_gate.stmts.U3(
            targets=tuple(qubit_idx_ssas),
            theta=stmt.theta,
            phi=stmt.phi,
            lam=stmt.lam,
        )
        stmt.replace_by(stim_stmt)

        return RewriteResult(has_done_something=True)
