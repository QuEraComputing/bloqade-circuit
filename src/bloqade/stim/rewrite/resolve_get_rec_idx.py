from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.record_idx_helper import GetRecIdxFromPredicate, GetRecIdxFromMeasurement
from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.analysis.measure_id.lattice import RecId


@dataclass
class ResolveGetRecIdx(RewriteRule):
    """Replace GetRecIdxFromMeasurement / GetRecIdxFromPredicate with computed constants.

    After MeasureIDAnalysis has produced RecId lattice elements for each helper
    statement, this rewrite reads RecId.idx (the final stim record index) and
    creates a py.Constant to replace all uses. The helper statement becomes
    unused and is cleaned up by DCE.
    """

    measure_id_frame: MeasureIDFrame

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if isinstance(node, (GetRecIdxFromMeasurement, GetRecIdxFromPredicate)):
            return self.resolve(node)
        return RewriteResult()

    def resolve(self, node: ir.Statement) -> RewriteResult:
        rec_id = self.measure_id_frame.entries.get(node.result)
        if not isinstance(rec_id, RecId):
            return RewriteResult()

        idx_const = py.Constant(rec_id.idx)
        idx_const.insert_before(node)
        node.result.replace_by(idx_const.result)

        return RewriteResult(has_done_something=True)
