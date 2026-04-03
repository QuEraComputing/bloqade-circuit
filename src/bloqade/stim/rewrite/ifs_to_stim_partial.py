from dataclasses import dataclass

from kirin import ir
from kirin.dialects import scf
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import gate
from bloqade.analysis.address import Address
from bloqade.record_idx_helper import GetRecIdxFromPredicate
from bloqade.stim.rewrite.util import insert_qubit_idx_from_address
from bloqade.stim.dialects.gate import CX as stim_CX, CY as stim_CY, CZ as stim_CZ
from bloqade.stim.dialects.auxiliary import GetRecord

PAULI_TO_CONTROLLED = {
    gate.stmts.X: stim_CX,
    gate.stmts.Y: stim_CY,
    gate.stmts.Z: stim_CZ,
}


@dataclass
class IfToStimPartial(RewriteRule):
    """Rewrite measurement-conditioned IfElse using GetRecIdxFromPredicate.

    Accepts the Bool condition directly (result of IsOne/IsZero) and creates
    GetRecIdxFromPredicate -> GetRecord -> CX/CY/CZ. If the body contains
    multiple Pauli gates, splits into multiple controlled gates sharing the
    same GetRecord result.
    """

    address_analysis: dict[ir.SSAValue, Address]

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if isinstance(node, scf.IfElse):
            return self.rewrite_IfElse(node)
        return RewriteResult()

    def rewrite_IfElse(self, stmt: scf.IfElse) -> RewriteResult:

        *body_stmts, _ = stmt.then_body.stmts()
        if not body_stmts:
            return RewriteResult()

        idx_from_predicate_calc = GetRecIdxFromPredicate(predicate_result=stmt.cond)
        idx_from_predicate_calc.insert_before(stmt)

        get_record_stmt = GetRecord(id=idx_from_predicate_calc.result)
        get_record_stmt.insert_before(stmt)

        for body_stmt in body_stmts:
            address = self.address_analysis.get(body_stmt.qubits)
            if address is None:
                return RewriteResult()

            qubit_idx_ssas = insert_qubit_idx_from_address(
                address=address, stmt_to_insert_before=stmt
            )
            if qubit_idx_ssas is None:
                return RewriteResult()

            stim_gate_cls = PAULI_TO_CONTROLLED[type(body_stmt)]
            stim_stmt = stim_gate_cls(
                targets=tuple(qubit_idx_ssas),
                controls=(get_record_stmt.result,) * len(qubit_idx_ssas),
            )
            stim_stmt.insert_before(stmt)

        stmt.delete()

        return RewriteResult(has_done_something=True)
