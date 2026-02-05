from kirin import ir
from kirin.dialects import py

from bloqade.stim.dialects import auxiliary
from bloqade.analysis.measure_id.lattice import RawMeasureId


def insert_get_records(
    node: ir.Statement, tuple_raw_measure_id: tuple[RawMeasureId, ...]
):
    """
    Insert GetRecord statements before the given node
    """
    get_record_ssas = []
    for known_measure_id in tuple_raw_measure_id:
        idx_stmt = py.constant.Constant(known_measure_id.idx)
        idx_stmt.insert_before(node)
        get_record_stmt = auxiliary.GetRecord(idx_stmt.result)
        get_record_stmt.insert_before(node)
        get_record_ssas.append(get_record_stmt.result)

    return get_record_ssas
