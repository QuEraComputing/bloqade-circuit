from dataclasses import field, dataclass

from kirin import ir
from typing_extensions import Self
from kirin.analysis.forward import Forward

from .lattice import Output


@dataclass
class OutputAnalysis(Forward):
    keys = ("bloqade.gemini.analysis.output",)
    lattice = Output

    num_physical_qubits: int = 7
    detector_count: int = field(init=False, default=0)

    def initialize(self) -> Self:
        self.detector_count = 0
        return super().initialize()

    def method_self(self, method: ir.Method):
        return Output.bottom()
