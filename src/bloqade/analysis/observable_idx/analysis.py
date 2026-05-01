from dataclasses import field, dataclass

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import ForwardExtra
from typing_extensions import Self
from kirin.analysis.forward import ForwardFrame


@dataclass
class ObservableIdxFrame(ForwardFrame[EmptyLattice]):
    observable_idx_at_stmt: dict[ir.Statement, int] = field(default_factory=dict)


class ObservableIdxAnalysis(ForwardExtra[ObservableIdxFrame, EmptyLattice]):
    """Assigns lexical-order observable indices to SetObservable statements.

    Lightweight Forward analysis whose only job is to number SetObservable
    statements consistently across rewrite stages. Runs cheaply on
    EmptyLattice (no per-SSA tracking, no convergence work beyond the
    trivial). Both SetObservablePartial and ResolveSetAnnotate read indices
    from the produced frame to share a single observable-index namespace.
    """

    keys = ["observable_idx"]
    lattice = EmptyLattice
    observable_count = 0

    def initialize(self) -> Self:
        self.observable_count = 0
        return super().initialize()

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> ObservableIdxFrame:
        return ObservableIdxFrame(node, has_parent_access=has_parent_access)

    def eval_fallback(
        self, frame: ObservableIdxFrame, node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        return tuple(self.lattice.bottom() for _ in node.results)

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()
