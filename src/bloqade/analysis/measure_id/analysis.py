from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import ForwardExtra
from kirin.analysis.forward import ForwardFrame

from .lattice import (
    MeasureId,
    NotMeasureId,
    RawMeasureId,
    MeasureIdTuple,
)


@dataclass
class GlobalRecordState:
    # every time a cond value is encountered inside scf
    # detach and save it here because I need to let it update
    # if it gets used again somewhere else
    type_for_scf_conds: dict[ir.Statement, MeasureId] = field(default_factory=dict)
    buffer: list[RawMeasureId] = field(default_factory=list)

    def add_record_idxs(self, num_new_records: int) -> MeasureIdTuple:
        # adjust all previous indices
        for record_idx in self.buffer:
            record_idx.idx -= num_new_records

        # generate new indices and add them to the buffer
        new_record_idxs = [RawMeasureId(-i) for i in range(num_new_records, 0, -1)]
        self.buffer += new_record_idxs
        # Return for usage, idxs linked to the global state
        return MeasureIdTuple(data=tuple(new_record_idxs))

    # Need for loop invariance, especially when you
    # run the loop twice "behind the scenes". Then
    # it isn't sufficient to just have two
    # copies of a lattice element point to one entry on the
    # buffer
    def clone_record_idxs(self, measure_id_tuple: MeasureIdTuple) -> MeasureIdTuple:
        cloned_members = []
        for raw_measure_id in measure_id_tuple.data:
            assert isinstance(raw_measure_id, RawMeasureId)
            cloned_raw_measure_id = RawMeasureId(raw_measure_id.idx)
            # put into the global buffer but also
            # return an analysis-facing copy
            self.buffer.append(cloned_raw_measure_id)
            cloned_members.append(cloned_raw_measure_id)
        return MeasureIdTuple(data=tuple(cloned_members))

    def offset_existing_records(self, offset: int):
        for record_idx in self.buffer:
            record_idx.idx -= offset


@dataclass
class MeasureIDFrame(ForwardFrame[MeasureId]):
    global_record_state: GlobalRecordState = field(default_factory=GlobalRecordState)
    # every time a cond value is encountered inside scf
    # detach and save it here because I need to let it update
    # if it gets used again somewhere else
    type_for_scf_conds: dict[ir.Statement, MeasureId] = field(default_factory=dict)
    measure_count_offset: int = 0


class MeasurementIDAnalysis(ForwardExtra[MeasureIDFrame, MeasureId]):

    keys = ["measure_id"]
    lattice = MeasureId

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> MeasureIDFrame:
        return MeasureIDFrame(node, has_parent_access=has_parent_access)

    # Still default to bottom,
    # but let constants return the softer "NoMeasureId" type from impl
    def eval_fallback(
        self, frame: ForwardFrame[MeasureId], node: ir.Statement
    ) -> tuple[MeasureId, ...]:
        return tuple(NotMeasureId() for _ in node.results)

    def method_self(self, method: ir.Method) -> MeasureId:
        return self.lattice.bottom()
