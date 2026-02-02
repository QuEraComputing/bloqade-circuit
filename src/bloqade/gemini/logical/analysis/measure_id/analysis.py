from dataclasses import field, dataclass

from bloqade.analysis.measure_id import MeasurementIDAnalysis


@dataclass
class LogicalMeasurementIdAnalysis(MeasurementIDAnalysis):
    """An address analysis for the Gemini logical dialect."""

    num_physical_qubits: int = field(kw_only=True)
