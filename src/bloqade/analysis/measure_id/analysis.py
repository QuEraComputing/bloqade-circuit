from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import ForwardExtra
from kirin.analysis.forward import ForwardFrame

from .lattice import MeasureId, NotMeasureId, KnownMeasureId


@dataclass
class GlobalRecordState:
    buffer: list[KnownMeasureId] = field(default_factory=list)

    # assume that this KnownMeasureId will always be -1
    def add_record_idxs(self, num_new_records: int) -> list[KnownMeasureId]:
        # adjust all previous indices
        for record_idx in self.buffer:
            record_idx.idx -= num_new_records

        # generate new indices and add them to the buffer
        new_record_idxs = [KnownMeasureId(-i) for i in range(num_new_records, 0, -1)]
        self.buffer += new_record_idxs
        # Return for usage, idxs linked to the global state
        return new_record_idxs


@dataclass
class MeasureIDFrame(ForwardFrame[MeasureId]):
    global_record_state: GlobalRecordState = field(default_factory=GlobalRecordState)


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
