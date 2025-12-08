from kirin import ir
from kirin.dialects import py

from bloqade.stim.dialects import auxiliary
from bloqade.analysis.measure_id.lattice import MeasureIdTuple, PredicatedMeasureId


def insert_get_records(node: ir.Statement, measure_id_tuple: MeasureIdTuple):
    """
    Insert GetRecord statements before the given node
    """
    get_record_ssas = []
    for known_measure_id in measure_id_tuple.data:
        assert isinstance(known_measure_id, PredicatedMeasureId)
        idx_stmt = py.constant.Constant(known_measure_id.idx)
        idx_stmt.insert_before(node)
        get_record_stmt = auxiliary.GetRecord(idx_stmt.result)
        get_record_stmt.insert_before(node)
        get_record_ssas.append(get_record_stmt.result)

    return get_record_ssas
