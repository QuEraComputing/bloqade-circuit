from typing import Callable
from dataclasses import field, dataclass

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward

from bloqade.squin.analysis.nsites import Sites

from ..address import Address

AlgorithmCallable = Callable[
    [list[tuple[tuple[int, int], ...]], int, tuple[int, int]],
    dict[int, tuple[int, int]],
]


@dataclass
class LayoutAnalysis(Forward):
    keys = ["circuit.layout"]
    lattice = EmptyLattice

    addr_analysis: dict[ir.SSAValue, Address]
    nsite_analysis: dict[ir.SSAValue, Sites]

    stages: list[tuple[tuple[int, int], ...]] = field(init=False, default_factory=list)

    def initialize(self):
        self.stages.clear()
        return super().initialize()

    def run_method(self, method: ir.Method, args: tuple[EmptyLattice, ...]):
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    def eval_stmt_fallback(self, frame, stmt):
        return (self.lattice.bottom(),)

    def get_layout(
        self,
        method: ir.Method,
        dimension: tuple[int, int],
        num_qubits: int,
        algorithm: AlgorithmCallable,
    ):
        self.run_analysis(method)
        raw_layout = algorithm(self.stages, num_qubits, dimension)
        return raw_layout
