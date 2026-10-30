from typing import Iterable
from dataclasses import dataclass

from kirin import ir
from kirin.dialects import py, scf
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.stim.dialects import auxiliary
from bloqade.record_idx_helper import GetRecIdxFromMeasurement
from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.stim.dialects.auxiliary import Detector, GetRecord
from bloqade.stim.rewrite.get_record_util import measurement_count
from bloqade.decoders.dialects.annotate.stmts import SetDetector


def extract_coord_ssas(
    node: ir.Statement,
) -> list[ir.SSAValue] | None:
    """Extract coordinate values from a SetDetector's coordinates argument
    and insert corresponding stim constant statements before the node.

    Returns the list of coord SSA values, or None if extraction fails.
    """
    if not isinstance(node.coordinates.owner, py.Constant):
        return None

    coord_values = node.coordinates.owner.value.unwrap()

    if not isinstance(coord_values, Iterable):
        return None

    if any(not isinstance(value, (int, float)) for value in coord_values):
        return None

    coord_ssas: list[ir.SSAValue] = []
    for coord_value in coord_values:
        if isinstance(coord_value, float):
            coord_stmt = auxiliary.ConstFloat(value=coord_value)
        else:
            coord_stmt = auxiliary.ConstInt(value=coord_value)
        coord_ssas.append(coord_stmt.result)
        coord_stmt.insert_before(node)

    return coord_ssas


@dataclass
class SetDetectorPartial(RewriteRule):
    """Rewrite SetDetector using GetRecIdxFromMeasurement placeholders.

    Instead of computing record indices from analysis results immediately, this injects
    GetRecIdxFromMeasurement statements that will be resolved post-analysis.
    `measure_id_frame` gives the number of measurements, as `measurement_count`
    describes.
    """

    measure_id_frame: MeasureIDFrame | None = None

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it is a `SetDetector`."""
        if isinstance(node, SetDetector):
            return self.rewrite_SetDetector(node)
        return RewriteResult()

    def rewrite_SetDetector(self, node: SetDetector) -> RewriteResult:
        """Replace `node` with a `Detector` that reads the record of each measurement.

        The rule leaves `node` if a loop returns its measurements, if its
        coordinates aren't constants, or if the number of measurements is unknown.
        """
        # A list that an scf.For returns holds the measurements of every
        # iteration. ResolveSetAnnotate resolves it later from the concrete
        # measurement IDs of the analysis, so this rule leaves it.
        if isinstance(node.measurements.owner, scf.For):
            return RewriteResult()

        coord_ssas = extract_coord_ssas(node)
        if coord_ssas is None:
            return RewriteResult()

        num_measurements = measurement_count(node.measurements, self.measure_id_frame)
        if num_measurements is None:
            return RewriteResult()

        get_record_ssas = []
        for measurement_idx in range(num_measurements):
            idx_const = py.Constant(measurement_idx)
            idx_const.insert_before(node)

            getitem_stmt = py.GetItem(obj=node.measurements, index=idx_const.result)
            getitem_stmt.insert_before(node)

            idx_from_measurement_calc = GetRecIdxFromMeasurement(
                measurement=getitem_stmt.result
            )
            idx_from_measurement_calc.insert_before(node)

            get_record_stmt = GetRecord(id=idx_from_measurement_calc.result)
            get_record_stmt.insert_before(node)

            get_record_ssas.append(get_record_stmt.result)

        detector_stmt = Detector(
            coord=tuple(coord_ssas), targets=tuple(get_record_ssas)
        )

        node.replace_by(detector_stmt)

        return RewriteResult(has_done_something=True)
