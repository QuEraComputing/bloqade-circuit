from kirin import ir, types
from kirin.dialects import py

from bloqade.stim.dialects import auxiliary
from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.analysis.measure_id.lattice import RawMeasureId, MeasureIdTuple


def insert_get_records(
    node: ir.Statement, measure_id_tuple: MeasureIdTuple, meas_count_at_stmt: int
):
    """
    Insert GetRecord statements before the given node
    """
    get_record_ssas = []
    for measure_id in measure_id_tuple.data:
        assert isinstance(measure_id, RawMeasureId)
        target_rec_idx = (measure_id.idx - 1) - meas_count_at_stmt
        idx_stmt = py.constant.Constant(target_rec_idx)
        idx_stmt.insert_before(node)
        get_record_stmt = auxiliary.GetRecord(idx_stmt.result)
        get_record_stmt.insert_before(node)
        get_record_ssas.append(get_record_stmt.result)

    return get_record_ssas


def measurement_count(
    measurements: ir.SSAValue, measure_id_frame: MeasureIDFrame | None
) -> int | None:
    """Return the number of measurements that `measurements` holds, or None.

    The count comes from the tuple that `MeasurementIDAnalysis` gives for
    `measurements`. Inside a loop, the analysis joins the values of all
    iterations, and the join of two tuples of different lengths gives no tuple.
    So a tuple there has the same length in every iteration. For example,
    `acc[-2:]` of a list `acc` that grows in a loop holds 2 measurements, although
    its type `IList[MeasurementResult, Any]` gives no length.

    The count needs kirin's loop fixpoint, which kirin 0.22.17 added. An older
    kirin runs a loop body once, so the tuple of the first iteration would stand
    for every iteration.

    Without a tuple in the frame, the literal length of the type gives the count.
    """
    if measure_id_frame is not None:
        value = measure_id_frame.entries.get(measurements)
        if isinstance(value, MeasureIdTuple):
            return len(value.data)
    kind = measurements.type
    if (
        isinstance(kind, types.Generic)
        and len(kind.vars) >= 2
        and isinstance(kind.vars[1], types.Literal)
        and isinstance(kind.vars[1].data, int)
    ):
        return kind.vars[1].data
    return None
