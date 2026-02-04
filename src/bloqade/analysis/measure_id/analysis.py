from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import ForwardExtra
from typing_extensions import Self
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

    # Still default to bottom,
    # but let constants return the softer "NoMeasureId" type from impl
    def eval_fallback(
        self, frame: ForwardFrame[MeasureId], node: ir.Statement
    ) -> tuple[MeasureId, ...]:
        return tuple(NotMeasureId() for _ in node.results)

    def method_self(self, method: ir.Method) -> MeasureId:
        return self.lattice.bottom()
