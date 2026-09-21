from typing import Generic, TypeVar, Callable, Hashable
from collections import Counter
from dataclasses import field, dataclass

from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.ir.nodes import Statement as Statement
from kirin.ir.method import Method as Method
from typing_extensions import Self
from kirin.analysis.forward import ForwardFrame

CounterKey = TypeVar("CounterKey", bound=Hashable)


@dataclass
class CountStatementAnalysis(Forward[EmptyLattice], Generic[CounterKey]):
    """Accumulate weighted counts for leaf statements in reachable IR.

    The analysis enters resolvable callees of ``func.Invoke`` and ``func.Call``
    once per call site. It also enters the callable of each supported higher-order
    ``ilist`` operation (``Map``, ``ForEach``, ``Foldl``, ``Foldr``, and ``Scan``)
    once per operation. Indirect calls whose callable cannot be resolved are
    skipped.

    Control flow is visited as written in the IR, not as executed:

    * ``scf.For`` — the loop body is counted **once**, regardless of trip count.
    * ``scf.IfElse`` — **both** the then and else branches are counted.

    A leaf statement is one handled through interpreter fallback rather than a
    dedicated traversal implementation. For each leaf, ``predicate`` returns
    either ``None`` or a ``(key, increment)`` pair. Each pair adds ``increment`` to
    ``counter[key]``. The key is caller-defined, so multiple statements or
    statement types can contribute to the same bucket. Dedicated call,
    control-flow, and ``ilist`` traversal operations are not themselves passed to
    ``predicate``.

    Unused nested callables are not visited. Calling ``run`` resets the counter.

    ## Usage examples

    ```
    from bloqade import squin
    from bloqade.analysis.count_statements import CountStatementAnalysis

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.x(q)

    def count_x(stmt):
        if isinstance(stmt, squin.gate.stmts.X):
            return "x", 1
        return None

    analysis = CountStatementAnalysis(main.dialects, count_x)
    analysis.run(main)
    analysis.counter  # Counter({"x": 1})
    ```
    """

    keys = ("count.statements",)
    lattice = EmptyLattice

    predicate: Callable[[Statement], tuple[CounterKey, int] | None]
    """Map a statement to a counter key and increment, or return ``None``."""
    counter: Counter[CounterKey] = field(default_factory=Counter)
    """Weighted totals grouped by the keys returned from ``predicate``."""

    def initialize(self) -> Self:
        """Reset interpreter state and discard counts from previous runs."""
        super().initialize()
        self.counter = Counter()
        return self

    def eval_fallback(self, frame: ForwardFrame[EmptyLattice], node: Statement) -> None:
        """Count a statement without a dedicated traversal implementation."""
        self.count_statement(node)

    def count_statement(self, node: Statement) -> None:
        """Add the contribution returned by ``predicate`` for ``node``."""
        result = self.predicate(node)
        if result is not None:
            key, increment = result
            self.counter[key] += increment

    def method_self(self, method: Method) -> EmptyLattice:
        """Represent a method's implicit ``self`` value with lattice bottom."""
        return EmptyLattice.bottom()
