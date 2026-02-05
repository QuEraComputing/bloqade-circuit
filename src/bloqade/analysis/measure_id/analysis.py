from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import ForwardExtra
from kirin.dialects import ilist
from typing_extensions import Self
from kirin.analysis.forward import ForwardFrame

from .lattice import (
    MeasureId,
    NotMeasureId,
    RawMeasureId,
    MeasureIdTuple,
)


@dataclass
class GlobalRecordState:
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
        return MeasureIdTuple(data=tuple(new_record_idxs), obj_type=ilist.IList)

    def clone_measure_id_tuple(
        self, measure_id_tuple: MeasureIdTuple
    ) -> MeasureIdTuple:
        cloned_members = []
        for measure_id in measure_id_tuple.data:
            cloned_measure_id = self.clone_measure_ids(measure_id)
            cloned_members.append(cloned_measure_id)
        return MeasureIdTuple(
            data=tuple(cloned_members),
            obj_type=measure_id_tuple.obj_type,
            predicate=measure_id_tuple.predicate,
        )

    def clone_raw_measure_id(self, raw_measure_id: RawMeasureId) -> RawMeasureId:
        cloned_raw_measure_id = RawMeasureId(
            raw_measure_id.idx, predicate=raw_measure_id.predicate
        )
        self.buffer.append(cloned_raw_measure_id)
        return cloned_raw_measure_id

    def clone_measure_ids(self, measure_id_type: MeasureId) -> MeasureId:
        if isinstance(measure_id_type, RawMeasureId):
            return self.clone_raw_measure_id(measure_id_type)
        elif isinstance(measure_id_type, MeasureIdTuple):
            return self.clone_measure_id_tuple(measure_id_type)
        return None

    def offset_existing_records(self, offset: int):
        for record_idx in self.buffer:
            record_idx.idx -= offset


@dataclass
class MeasureIDFrame(ForwardFrame[MeasureId]):
    global_record_state: GlobalRecordState = field(default_factory=GlobalRecordState)
    type_for_scf_conds: dict[ir.Statement, MeasureId] = field(default_factory=dict)
    measure_count_offset: int = 0


class MeasurementIDAnalysis(ForwardExtra[MeasureIDFrame, MeasureId]):

    keys = ["measure_id"]
    lattice = MeasureId
    measure_count = 0
    detector_count = 0
    observable_count = 0

    def initialize(self) -> Self:
        self.measure_count = 0
        self.detector_count = 0
        self.observable_count = 0
        return super().initialize()

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> MeasureIDFrame:
        return MeasureIDFrame(node, has_parent_access=has_parent_access)

    def eval_fallback(
        self, frame: ForwardFrame[MeasureId], node: ir.Statement
    ) -> tuple[MeasureId, ...]:
        return tuple(NotMeasureId() for _ in node.results)

    def method_self(self, method: ir.Method) -> MeasureId:
        return self.lattice.bottom()
