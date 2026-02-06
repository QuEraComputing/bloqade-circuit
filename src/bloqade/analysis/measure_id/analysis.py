from typing import Iterable
from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import ForwardExtra
from kirin.dialects import ilist
from typing_extensions import Self
from kirin.analysis.forward import ForwardFrame

from .lattice import (
    MeasureId,
    MutableIdx,
    NotMeasureId,
    RawMeasureId,
    MeasureIdTuple,
)


@dataclass
class GlobalRecordState:
    type_for_scf_conds: dict[ir.Statement, MeasureId] = field(default_factory=dict)
    buffer: list[MutableIdx] = field(default_factory=list)

    def add_record_idxs(self, num_new_records: int) -> MeasureIdTuple:
        # Adjust all previous indices
        for mutable_idx in self.buffer:
            mutable_idx.value -= num_new_records

        # Generate new MutableIdx entries and add to buffer
        new_mutable_idxs = [MutableIdx(-i) for i in range(num_new_records, 0, -1)]
        self.buffer += new_mutable_idxs

        # Create RawMeasureIds referencing these MutableIdxs
        new_record_idxs = [RawMeasureId(idx) for idx in new_mutable_idxs]
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
        )

    def clone_raw_measure_id(self, raw_measure_id: RawMeasureId) -> RawMeasureId:
        # Create new MutableIdx for independent tracking
        new_mutable_idx = MutableIdx(raw_measure_id.idx)
        self.buffer.append(new_mutable_idx)

        # Return RawMeasureId with same predicate, referencing new MutableIdx
        return RawMeasureId(new_mutable_idx, predicate=raw_measure_id.predicate)

    def clone_measure_ids(self, measure_id_type: MeasureId) -> MeasureId:
        if isinstance(measure_id_type, RawMeasureId):
            return self.clone_raw_measure_id(measure_id_type)
        elif isinstance(measure_id_type, MeasureIdTuple):
            return self.clone_measure_id_tuple(measure_id_type)
        return None

    def offset_existing_records(self, offset: int):
        for mutable_idx in self.buffer:
            mutable_idx.value -= offset

    def add_unique_mutable_idxs(self, mutable_idxs: Iterable[MutableIdx]) -> None:
        """Add MutableIdx objects to buffer, skipping duplicates."""
        existing = set(self.buffer)
        for idx in mutable_idxs:
            if idx not in existing:
                existing.add(idx)
                self.buffer.append(idx)


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
