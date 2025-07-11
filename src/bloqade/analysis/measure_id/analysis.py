from typing import TypeVar

from kirin import ir, interp
from kirin.analysis import Forward, const
from kirin.analysis.forward import ForwardFrame

from .lattice import MeasureId, NotMeasureId


class MeasurementIDAnalysis(Forward[MeasureId]):

    keys = ["measure_id"]
    lattice = MeasureId
    # for every kind of measurement encountered, increment this
    # then use this to generate the negative values for target rec indices
    measure_count = 0

    # Still default to bottom,
    # but let constants return the softer "NoMeasureId" type from impl
    def eval_stmt_fallback(
        self, frame: ForwardFrame[MeasureId], stmt: ir.Statement
    ) -> tuple[MeasureId, ...]:
        return tuple(NotMeasureId() for _ in stmt.results)

    def run_method(self, method: ir.Method, args: tuple[MeasureId, ...]):
        # NOTE: we do not support dynamic calls here, thus no need to propagate method object
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    T = TypeVar("T")

    # Xiu-zhe (Roger) Luo came up with this in the address analysis,
    # reused here for convenience
    # TODO: Remove this function once upgrade to kirin 0.18 happens,
    #       method is built-in to interpreter then
    def get_const_value(self, input_type: type[T], value: ir.SSAValue) -> T:
        if isinstance(hint := value.hints.get("const"), const.Value):
            data = hint.data
            if isinstance(data, input_type):
                return hint.data
            raise interp.InterpreterError(
                f"Expected constant value <type = {input_type}>, got {data}"
            )
        raise interp.InterpreterError(
            f"Expected constant value <type = {input_type}>, got {value}"
        )
