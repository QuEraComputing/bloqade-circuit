from typing import Callable
from collections import Counter
from dataclasses import field, dataclass

from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.ir.nodes import Statement as Statement
from kirin.ir.method import Method as Method
from typing_extensions import Self
from kirin.analysis.forward import ForwardFrame


@dataclass
class CountStatementAnalysis(Forward[EmptyLattice]):
    """Count matching statements by walking reachable IR.

    Enters callees (``func.Invoke`` / ``func.Call``) and higher-order
    ``ilist`` functions (``Map`` / ``ForEach`` / ``Foldl`` / ``Foldr`` /
    ``Scan``), each **once**. Control-flow is visited as written
    in the IR, not as executed:

    * ``scf.For`` — the loop body is counted **once**, regardless of trip count.
    * ``scf.IfElse`` — **both** the then and else branches are counted.

    Each matching statement increments ``counter[statement]`` by ``increment`` every
    time the walk visits it (so two call sites of the same kernel count twice).
    Unused nested kernels are not visited. ``run`` resets the counters.

    The ``predicate`` returns ``(matched, increment)``.

    ## Usage examples

    ```
    from bloqade import squin
    from bloqade.analysis.count_statements import CountStatementAnalysis

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.x(q)

    def count_x(stmt):
        return isinstance(stmt, squin.gate.stmts.X), 1

    counter = CountStatementAnalysis(main.dialects, count_x)
    counter.run(main)
    print(counter.counter)
    ```
    """

    keys = ("count.statements",)
    lattice = EmptyLattice

    predicate: Callable[[Statement], tuple[bool, int]]
    """``(matched, increment)`` for each visited statement."""
    counter: Counter[type] = field(default_factory=Counter)
    """Number of times each matching statement was visited."""

    def initialize(self) -> Self:
        """initializing resets counters"""
        super().initialize()
        self.counter = Counter()
        return self

    def eval_fallback(self, frame: ForwardFrame[EmptyLattice], node: Statement) -> None:
        """logic is handled in the fallback"""
        self.count_statement(node)

    def count_statement(self, node: Statement) -> None:
        """this is the actual counting logic, so we don't need to add dedicated impls for statements"""
        matched, increment = self.predicate(node)
        if matched:
            self.counter[type(node)] += increment

    def method_self(self, method: Method) -> EmptyLattice:
        """always return bottom for self"""
        return EmptyLattice.bottom()
