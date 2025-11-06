from typing import Iterable
from dataclasses import dataclass

from kirin import ir
from kirin.dialects.py import Constant
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.stim.dialects import auxiliary
from bloqade.annotate.stmts import SetDetector
from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.stim.dialects.auxiliary import Detector
from bloqade.analysis.measure_id.lattice import MeasureIdTuple

from ..rewrite.get_record_util import insert_get_records


@dataclass
class SetDetectorToStim(RewriteRule):
    """
    Rewrite SetDetector to GetRecord and Detector in the stim dialect
    """

    measure_id_frame: MeasureIDFrame

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        match node:
            case SetDetector():
                return self.rewrite_SetDetector(node)
            case _:
                return RewriteResult()

    def rewrite_SetDetector(self, node: SetDetector) -> RewriteResult:

        # get coordinates and generate correct consts
        coord_ssas = []
        if not isinstance(node.coordinates.owner, Constant):
            return RewriteResult()

        coord_values = node.coordinates.owner.value.unwrap()

        if not isinstance(coord_values, Iterable):
            return RewriteResult()

        if any(not isinstance(value, (int, float)) for value in coord_values):
            return RewriteResult()

        for coord_value in coord_values:
            if isinstance(coord_value, float):
                coord_stmt = auxiliary.ConstFloat(value=coord_value)
            else:  # int
                coord_stmt = auxiliary.ConstInt(value=coord_value)
            coord_ssas.append(coord_stmt.result)
            coord_stmt.insert_before(node)

        measure_ids = self.measure_id_frame.entries[node.inputs]
        assert isinstance(measure_ids, MeasureIdTuple)

        get_record_list = insert_get_records(
            node, measure_ids, self.measure_id_frame.num_measures_at_stmt[node]
        )

        detector_stmt = Detector(
            coord=tuple(coord_ssas), targets=tuple(get_record_list)
        )

        node.replace_by(detector_stmt)

        return RewriteResult(has_done_something=True)
