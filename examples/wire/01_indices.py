"""Print symbolic qubit indices inside a loop."""

from bloqade import squin
from bloqade.analysis.indices import IndexExpr, KnownIndex, IndexAnalysis


@squin.kernel
def bell_pairs(n: int):
    """Prepare n adjacent Bell pairs for n between zero and four."""
    qs = squin.qalloc(8)
    for i in range(n):
        left = 2 * i
        for j in range(2):
            right = left * j + 1
            squin.h(qs[left])
            squin.cx(qs[left], qs[right])


if __name__ == "__main__":
    n = bell_pairs.callable_region.blocks[0].args[1]
    frame, _ = IndexAnalysis(bell_pairs.dialects).run(
        bell_pairs, KnownIndex(IndexExpr.of(n))
    )
    analysis = frame.entries
    bell_pairs.print(analysis=analysis)
