from typing import TypeVar
from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import ForwardExtra, const
from kirin.analysis.forward import ForwardFrame

from .lattice import MeasureId, NotMeasureId


@dataclass
class MeasureIDFrame(ForwardFrame[MeasureId]):
    num_measures_at_stmt: dict[ir.Statement, int] = field(default_factory=dict)


class MeasurementIDAnalysis(ForwardExtra[MeasureIDFrame, MeasureId]):

    keys = ["measure_id"]
    lattice = MeasureId
    # for every kind of measurement encountered, increment this
    # then use this to generate the negative values for target rec indices
    measure_count = 0

    def initialize_frame(
        self, code: ir.Statement, *, has_parent_access: bool = False
    ) -> MeasureIDFrame:
        return MeasureIDFrame(code, has_parent_access=has_parent_access)

    # Still default to bottom,
    # but let constants return the softer "NoMeasureId" type from impl
    def eval_stmt_fallback(
        self, frame: ForwardFrame[MeasureId], stmt: ir.Statement
    ) -> tuple[MeasureId, ...]:
        return tuple(NotMeasureId() for _ in stmt.results)

    def run_method(self, method: ir.Method, args: tuple[MeasureId, ...]):
        # NOTE: we do not support dynamic calls here, thus no need to propagate method object
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    # Xiu-zhe (Roger) Luo came up with this in the address analysis,
    # reused here for convenience (now modified to be a bit more graceful)
    # TODO: Remove this function once upgrade to kirin 0.18 happens,
    #       method is built-in to interpreter then

    T = TypeVar("T")

    def get_const_value(
        self, input_type: type[T], value: ir.SSAValue
    ) -> type[T] | None:
        if isinstance(hint := value.hints.get("const"), const.Value):
            data = hint.data
            if isinstance(data, input_type):
                return hint.data

        return None
