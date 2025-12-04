from typing import Any
from dataclasses import field, dataclass

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward, ForwardFrame
from kirin.validation import ValidationPass

from bloqade.analysis import address, measure_id


@dataclass
class _GeminiTerminalMeasurementValidationAnalysis(Forward[EmptyLattice]):
    keys = ("gemini.validate.terminal_measurement",)

    measurement_analysis_results: ForwardFrame
    unique_qubits_allocated: int = 0
    terminal_measurement_encountered: bool = False
    lattice = EmptyLattice

    # boilerplate, not really worried about these right now
    def eval_fallback(self, frame: ForwardFrame, node: ir.Statement):
        return tuple(self.lattice.bottom() for _ in range(len(node.results)))

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()


@dataclass
class GeminiTerminalMeasurementValidation(ValidationPass):

    analysis_cache: dict = field(default_factory=dict)

    def name(self) -> str:
        return "Gemini Terminal Measurement Validation"

    def get_required_analyses(self) -> list[type]:
        return [measure_id.MeasurementIDAnalysis]

    def set_analysis_cache(self, cache: dict[type, Any]) -> None:
        self.analysis_cache.update(cache)

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:

        # get the data out of the cache and forward it to the underlying analysis
        measurement_analysis_results = self.analysis_cache.get(
            measure_id.MeasurementIDAnalysis
        )

        address_analysis = address.AddressAnalysis(dialects=method.dialects)
        address_analysis.run(method)
        unique_qubits_allocated = address_analysis.qubit_count

        assert (
            measurement_analysis_results is not None
        ), "Measurement ID analysis results not found in cache"

        analysis = _GeminiTerminalMeasurementValidationAnalysis(
            method.dialects,
            measurement_analysis_results,
            unique_qubits_allocated=unique_qubits_allocated,
        )

        frame, _ = analysis.run(method)

        return frame, analysis.get_validation_errors()
