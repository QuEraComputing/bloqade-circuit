from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import ForwardExtra
from kirin.analysis.forward import ForwardFrame

from .lattice import Record, RecordIdx, RecordTuple


@dataclass
class GlobalRecordState:
    buffer: list[RecordIdx] = field(default_factory=list)

    # assume that this RecordIdx will always be -1
    def add_record_idxs(self, num_new_records: int, id: int) -> list[RecordIdx]:
        # adjust all previous indices
        for record_idx in self.buffer:
            record_idx.idx -= num_new_records

        # generate new indices and add them to the buffer
        new_record_idxs = [RecordIdx(-i, id) for i in range(num_new_records, 0, -1)]
        self.buffer += new_record_idxs
        # Return for usage, idxs linked to the global state
        return new_record_idxs

    # Need for loop invariance, especially when you
    # run the loop twice "behind the scenes". Then
    # it isn't sufficient to just have two
    # copies of a lattice element point to one entry on the
    # buffer
    def clone_record_idxs(self, record_tuple: RecordTuple, id: int) -> RecordTuple:
        cloned_members = []
        for record_idx in record_tuple.members:
            cloned_record_idx = RecordIdx(record_idx.idx, id)
            # put into the global buffer but also
            # return an analysis-facing copy
            self.buffer.append(cloned_record_idx)
            cloned_members.append(cloned_record_idx)

        return RecordTuple(members=tuple(cloned_members))

    def offset_existing_records(self, offset: int):
        for record_idx in self.buffer:
            record_idx.idx -= offset

    """
    Might need a free after use! You can keep the size of the list small
    but could be a premature optimization...
    """
    # def drop_record_idxs(self, record_tuple: RecordTuple):
    #    for record_idx in record_tuple.members:
    #        self.buffer.remove(record_idx)


@dataclass
class RecordFrame(ForwardFrame):
    global_record_state: GlobalRecordState = field(default_factory=GlobalRecordState)
    measure_count_offset: int = 0
    frame_id: int = 0


class RecordAnalysis(ForwardExtra[RecordFrame, Record]):
    keys = ["record"]
    lattice = Record

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> RecordFrame:
        return RecordFrame(node, has_parent_access=has_parent_access)

    def eval_fallback(
        self, frame: RecordFrame, node: ir.Statement
    ) -> tuple[Record, ...]:
        return tuple(self.lattice.bottom() for _ in node.results)

    def run_method(self, method, args: tuple[Record, ...]):
        # NOTE: we do not support dynamic calls here, thus no need to propagate method object
        return self.run_method(method.code, (self.lattice.bottom(),) + args)

    def method_self(self, method: ir.Method) -> Record:
        return self.lattice.bottom()
