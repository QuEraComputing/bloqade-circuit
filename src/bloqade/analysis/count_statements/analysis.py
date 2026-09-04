from typing import Callable
from dataclasses import dataclass

from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.ir.nodes import Statement as Statement
from kirin.ir.method import Method as Method
from typing_extensions import Self
from kirin.analysis.forward import ForwardFrame


@dataclass
class CountStatementAnalysis(Forward[EmptyLattice]):
    """Count matching statements by walking reachable IR.

    Enters callees (``func.Invoke`` / ``func.Call``) and mapped functions
    (``ilist.Map`` / ``ilist.ForEach``). Control-flow is visited as written
    in the IR, not as executed:

    * ``scf.For`` — the loop body is counted **once**, regardless of trip count.
    * ``scf.IfElse`` — **both** the then and else branches are counted.

    Each matching statement increments ``counts[idx]`` by ``increment`` every
    time the walk visits it (so two call sites of the same kernel count twice).
    Unused nested kernels are not visited. ``run`` resets the counters.

    The ``predicate`` returns ``(matched, idx, increment)``. ``N`` is the
    number of counter buckets.

    ## Usage examples

    ```
    from bloqade import squin
    from bloqade.analysis.count_statements import CountStatementAnalysis

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.x(q)

    def count_x(stmt):
        return isinstance(stmt, squin.gate.stmts.X), 0, 1

    counter = CountStatementAnalysis(main.dialects, count_x, N=1)
    counter.run(main)
    counter.counts  # [1]
    ```
    """

    keys = ("count.statements",)
    lattice = EmptyLattice

    predicate: Callable[[Statement], tuple[bool, int, int]]
    """``(matched, idx, increment)`` for each visited statement."""
    N: int = 1
    """Number of counter buckets in ``counts``."""

    def __post_init__(self) -> None:
        """set counters here so they exist as attribute on the class"""
        super().__post_init__()
        self.counts = [0 for _ in range(self.N)]

    def initialize(self) -> Self:
        """initializing resets counters"""
        super().initialize()
        self.counts = [0 for _ in range(self.N)]
        return self

    def eval_fallback(self, frame: ForwardFrame[EmptyLattice], node: Statement) -> None:
        """this is the actual counting logic, so we don't need to add dedicated impls for statements"""
        matched, idx, increment = self.predicate(node)
        if matched:
            self.counts[idx] += increment

    def method_self(self, method: Method) -> EmptyLattice:
        """always return bottom for self"""
        return EmptyLattice.bottom()
