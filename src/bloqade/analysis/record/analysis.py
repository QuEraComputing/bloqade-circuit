from typing import TypeVar
from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import ForwardExtra, const
from kirin.analysis.forward import ForwardFrame

from .lattice import Record, RecordIdx


@dataclass
class GlobalRecordState:
    stack: list[RecordIdx] = field(default_factory=list)

    # assume that this RecordIdx will always be -1
    def increment_record_idx(self) -> RecordIdx:
        # adjust all previous indices
        for record_idx in self.stack:
            record_idx.idx -= 1
        self.stack.append(RecordIdx(-1))
        # Return for usage
        return self.stack[-1]

    def drop_record_idx(self, record_to_drop: RecordIdx):
        # there is a chance now that the ordering is messed up but
        # we can now update the indices to enforce consistency.
        # We only have to update UP to the entry that was just removed
        # everything else maintains ordering
        dropped_idx = record_to_drop.idx
        self.stack.remove(record_to_drop)
        for record_idx in self.stack:
            if record_idx.idx < dropped_idx:
                record_idx.idx += 1


@dataclass
class RecordFrame(ForwardFrame):
    global_record_state: GlobalRecordState = field(default_factory=GlobalRecordState)


class RecordAnalysis(ForwardExtra[RecordFrame, Record]):
    keys = ["record"]
    lattice = Record

    def initialize_frame(self, code, *, has_parent_access: bool = False) -> RecordFrame:
        return RecordFrame(code, has_parent_access=has_parent_access)

    def eval_stmt_fallback(self, frame: RecordFrame, stmt) -> tuple[Record, ...]:
        return tuple(self.lattice.bottom() for _ in stmt.results)

    def run_method(self, method, args: tuple[Record, ...]):
        # NOTE: we do not support dynamic calls here, thus no need to propagate method object
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    T = TypeVar("T")

    def get_const_value(
        self, input_type: type[T], value: ir.SSAValue
    ) -> type[T] | None:
        if isinstance(hint := value.hints.get("const"), const.Value):
            data = hint.data
            if isinstance(data, input_type):
                return hint.data

        return None
