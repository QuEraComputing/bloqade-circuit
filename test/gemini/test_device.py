from kirin import types
from kirin.dialects import ilist

from bloqade import squin
from bloqade.gemini import logical
from bloqade.decoders.dialects.annotate.stmts import SetDetector
from bloqade.gemini.logical.rewrite.remove_postprocessing import (
    RemovePostProcessing,
)


def test_remove_postprocessing():
    @logical.kernel(aggressive_unroll=True)
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)

        m = logical.terminal_measure(q)
        return m

    result = RemovePostProcessing(main.dialects)(main)

    assert result.has_done_something

    # check that calling twice doesn't do anything
    result = RemovePostProcessing(main.dialects)(main)
    assert not result.has_done_something

    main.print()
    assert main.return_type.is_subseteq(types.NoneType)


def test_remove_postprocessing_with_uses():
    @logical.kernel(aggressive_unroll=True)
    def main():
        q = squin.qalloc(2)
        m = logical.terminal_measure(q)
        det = squin.set_detector(ilist.IList([m[0][0], m[1][0]]), [0, 1])
        return det

    # check that we have a detector there
    assert any(isinstance(stmt, SetDetector) for stmt in main.callable_region.stmts())

    result = RemovePostProcessing(main.dialects)(main)
    assert result.has_done_something

    assert main.return_type.is_subseteq(types.NoneType)

    # check that calling twice doesn't do anything
    result = RemovePostProcessing(main.dialects)(main)
    assert not result.has_done_something

    assert not any(
        isinstance(stmt, SetDetector) for stmt in main.callable_region.stmts()
    )
