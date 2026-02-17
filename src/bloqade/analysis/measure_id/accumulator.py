"""
Helper functions for detecting accumulator semantics
(chiefly the pattern of using lists to store a growing number of measurements)
and expanding them with the correct number of RawMeasureId objects in the correct order.
"""

from kirin import ir
from kirin.dialects import py, scf

from .util import get_scf_for_repeat_count
from .lattice import (
    MeasureId,
    MutableIdx,
    AnyMeasureId,
    RawMeasureId,
    MeasureIdTuple,
)
from .analysis import MeasureIDFrame


def is_growing_accumulator(
    init_var: MeasureId,
    first_var: MeasureId,
    second_var: MeasureId,
) -> bool:
    if not (
        isinstance(init_var, MeasureIdTuple)
        and isinstance(first_var, MeasureIdTuple)
        and isinstance(second_var, MeasureIdTuple)
    ):
        return False

    first_growth = len(first_var.data) - len(init_var.data)
    second_growth = len(second_var.data) - len(first_var.data)
    return first_growth > 0 and first_growth == second_growth


def detect_append_order_from_ir(
    stmt: scf.stmts.For,
    var_idx: int,
) -> bool | None:
    """Detect append vs prepend by inspecting the py.Add in the loop body.

    Returns True for append (acc + ms), False for prepend (ms + acc),
    or None if the pattern cannot be determined from the IR.
    """
    body_block = stmt.body.blocks[0]
    acc_block_arg = body_block.args[var_idx + 1]

    yield_stmt = body_block.last_stmt
    if not isinstance(yield_stmt, scf.stmts.Yield):
        return None

    yielded_val = yield_stmt.values[var_idx]
    if not isinstance(yielded_val, ir.ResultValue):
        return None

    add_stmt = yielded_val.owner
    if not isinstance(add_stmt, py.Add):
        return None

    if add_stmt.lhs is acc_block_arg:
        return True
    if add_stmt.rhs is acc_block_arg:
        return False
    return None


def expand_accumulator(
    stmt: scf.stmts.For,
    frame: MeasureIDFrame,
    init_var: MeasureIdTuple,
    first_var: MeasureIdTuple,
    is_append: bool,
) -> MeasureId:
    """Expand a growing accumulator to its final concrete MeasureIdTuple.

    Uses the statically known loop count to compute the total number of
    accumulated measurements and constructs the final tuple with correct
    MutableIdx values registered in the parent GlobalRecordState.
    """
    num_iterations = get_scf_for_repeat_count(stmt)
    if num_iterations is None:
        return AnyMeasureId()

    measurements_per_iter = len(first_var.data) - len(init_var.data)
    total_new_measurements = num_iterations * measurements_per_iter

    frame.global_record_state.offset_existing_records(total_new_measurements)

    new_mutable_idxs = [MutableIdx(-i) for i in range(total_new_measurements, 0, -1)]
    frame.global_record_state.buffer.extend(new_mutable_idxs)
    new_raw_ids = [RawMeasureId(idx) for idx in new_mutable_idxs]

    if is_append:
        final_data = init_var.data + tuple(new_raw_ids)
    else:
        # you're prepending here, so your ordering is "staggered"
        # ex: acc = ms + acc where acc is (-3, -2, -1)
        # the ms happens on 3 qubits that bumps your existing acc to (-6, -5, -4)
        # then you need to add your (-3, -2, -1) to the FRONT of the tuple so it looks like (-3, -2, -1, -6, -5, -4)
        chunks: list[RawMeasureId] = []
        for i in range(num_iterations - 1, -1, -1):
            chunk = new_raw_ids[
                i * measurements_per_iter : (i + 1) * measurements_per_iter
            ]
            chunks.extend(chunk)
        final_data = tuple(chunks) + init_var.data

    return MeasureIdTuple(data=final_data, obj_type=first_var.obj_type)
