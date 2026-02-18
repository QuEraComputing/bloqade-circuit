import numpy as np
from kirin import types
from kirin.dialects import ilist

from bloqade import squin
from bloqade.gemini import GeminiLogicalDevice, logical
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


def test_split_postprocessing():
    @logical.kernel(aggressive_unroll=True, num_physical_qubits=6)
    def main():
        q = squin.qalloc(2)
        squin.x(q[0])
        m = logical.terminal_measure(q)
        det = squin.set_detector(ilist.IList([m[0][0], m[1][0]]), [0, 1])
        return det

    device = GeminiLogicalDevice()

    execution_kernel, postprocessing_func = device.split_execution_from_postprocessing(
        main
    )

    assert execution_kernel.return_type.is_subseteq(types.NoneType)
    assert postprocessing_func is not None

    task = device.task(main)

    future = task.run_async()
    assert future.postprocessing_function is not None

    result = future.result()
    raw_result = future._physical_result()

    expected_raw_results = [True] * 6
    expected_raw_results.extend([False] * 6)

    assert (raw_result == np.array([expected_raw_results])).all()

    assert result == [True]
    assert result == list(postprocessing_func(raw_result))


def test_return_measure():
    @logical.kernel(aggressive_unroll=True)
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)

        m = logical.terminal_measure(q)
        return m

    device = GeminiLogicalDevice()

    task = device.task(main)

    nshots = 23
    future = task.run_async(shots=nshots)

    results = future.result()

    assert len(results) == nshots

    for res in results:
        assert len(res) == 2
        assert len(res[0]) == len(res[1])
        for bits in res:
            assert all(bits) or not any(bits)
