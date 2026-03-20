from dataclasses import field, dataclass

from kirin import ir
from kirin.interp import StatementResult
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

    def frame_eval(
        self, frame: MeasureIDFrame, node: ir.Statement
    ) -> StatementResult[MeasureId]:
        method = self.lookup_registry(frame, node)
        if method is not None:
            return method(self, frame, node)
        return self.eval_fallback(frame, node)

    def method_self(self, method: ir.Method) -> MeasureId:
        return self.lattice.bottom()
