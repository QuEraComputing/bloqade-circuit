from kirin import ir
from kirin.dialects import py

from bloqade.stim.dialects import auxiliary
from bloqade.analysis.measure_id.lattice import MeasureIdBool, MeasureIdTuple


def insert_get_records(
    node: ir.Statement, measure_id_tuple: MeasureIdTuple, meas_count_at_stmt: int
):
    """
    Insert GetRecord statements before the given node
    """
    get_record_ssas = []
    for measure_id_bool in measure_id_tuple.data:
        assert isinstance(measure_id_bool, MeasureIdBool)
        target_rec_idx = (measure_id_bool.idx - 1) - meas_count_at_stmt
        idx_stmt = py.constant.Constant(target_rec_idx)
        idx_stmt.insert_before(node)
        get_record_stmt = auxiliary.GetRecord(idx_stmt.result)
        get_record_stmt.insert_before(node)
        get_record_ssas.append(get_record_stmt.result)

    return get_record_ssas
