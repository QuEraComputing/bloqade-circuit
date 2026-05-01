"""Tests for loop-grown accumulator patterns lowering to Stim.

Covers:
- Post-loop consumption (existing, well-supported): bare and indexed.
- In-loop consumption (new): index/slice into the loop-grown accumulator
  inside the body, where REPEAT-faithfulness depends on the consumption
  pattern (faithful: negative indices for append-grown, positive indices
  for prepend-grown, and equivalent slices).
"""

import io

from kirin import ir

from bloqade import stim, squin
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass


def codegen(mt: ir.Method):
    buf = io.StringIO()
    emit = EmitStimMain(dialects=stim.main, io=buf)
    emit.initialize()
    emit.run(mt)
    return buf.getvalue().strip()


def load_reference_program(filename):
    import os

    path = os.path.join(
        os.path.dirname(__file__), "stim_reference_programs", "scf_for", filename
    )
    with open(path, "r") as f:
        return f.read()


# -------------------------------------------------------------------------
# Existing accumulator tests (post-loop consumption). Moved verbatim from
# test_scf_for_to_repeat.py; reference .stim files remain under
# stim_reference_programs/scf_for/.
# -------------------------------------------------------------------------


def test_accumulator_append_empty_init():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_append_empty_init.stim").rstrip()
    )


def test_accumulator_prepend_empty_init():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_prepend_empty_init.stim").rstrip()
    )


def test_accumulator_append_initialized():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_append_initialized.stim").rstrip()
    )


def test_accumulator_prepend_initialized():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_prepend_initialized.stim").rstrip()
    )


def test_accumulator_append_empty_init_all_iters():
    """Accessing measurements from every iteration, not just the first."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])
        squin.set_detector([acc[2], acc[3]], coordinates=[1, 0])
        squin.set_detector([acc[4], acc[5]], coordinates=[2, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_append_empty_init_all_iters.stim"
        ).rstrip()
    )


def test_accumulator_prepend_empty_init_all_iters():
    """Accessing measurements from every iteration via prepend, not just the last."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])
        squin.set_detector([acc[2], acc[3]], coordinates=[1, 0])
        squin.set_detector([acc[4], acc[5]], coordinates=[2, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_prepend_empty_init_all_iters.stim"
        ).rstrip()
    )


def test_accumulator_append_initialized_all_iters():
    """Accessing measurements from initial + every loop iteration."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])
        squin.set_detector([acc[2], acc[3]], coordinates=[1, 0])
        squin.set_detector([acc[4], acc[5]], coordinates=[2, 0])
        squin.set_detector([acc[6], acc[7]], coordinates=[3, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_append_initialized_all_iters.stim"
        ).rstrip()
    )


def test_accumulator_prepend_initialized_all_iters():
    """Accessing measurements from every loop iteration + initial via prepend."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])
        squin.set_detector([acc[2], acc[3]], coordinates=[1, 0])
        squin.set_detector([acc[4], acc[5]], coordinates=[2, 0])
        squin.set_detector([acc[6], acc[7]], coordinates=[3, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_prepend_initialized_all_iters.stim"
        ).rstrip()
    )


def test_accumulator_set_observable_whole_list():
    """Regression for PR #736: set_observable(acc) where acc is a loop-grown
    accumulator. Must emit 8 record references, not 2."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_observable(acc)

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_set_observable_whole_list.stim").rstrip()
    )


def test_accumulator_set_detector_whole_list():
    """Sibling of the set_observable case: SetDetectorPartial has the same
    type.vars[1] vulnerability as SetObservablePartial. Must emit 8 record
    references."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector(acc, coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_set_detector_whole_list.stim").rstrip()
    )


def test_accumulator_prepend_initialized_set_observable_whole_list():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_observable(acc)

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_prepend_initialized_set_observable.stim"
        ).rstrip()
    )


def test_accumulator_prepend_initialized_set_detector_whole_list():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_detector(acc, coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_prepend_initialized_set_detector.stim"
        ).rstrip()
    )


def test_accumulator_append_empty_init_set_observable_whole_list():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_observable(acc)

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_append_empty_init_set_observable.stim"
        ).rstrip()
    )


def test_accumulator_append_empty_init_set_detector_whole_list():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector(acc, coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_append_empty_init_set_detector.stim"
        ).rstrip()
    )


def test_accumulator_prepend_empty_init_set_observable_whole_list():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_observable(acc)

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_prepend_empty_init_set_observable.stim"
        ).rstrip()
    )


def test_accumulator_prepend_empty_init_set_detector_whole_list():
    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        squin.set_detector(acc, coordinates=[0, 0])

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program(
            "accumulator_prepend_empty_init_set_detector.stim"
        ).rstrip()
    )


def test_accumulator_mixed_patterns():
    """Same accumulator used both via constant-index (partial rewrite path)
    AND as bare aggregate (new resolver path) in one kernel."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        squin.set_detector([acc[0], acc[1]], coordinates=[0, 0])
        squin.set_observable(acc)

    SquinToStimPass(dialects=test.dialects)(test)
    assert (
        codegen(test)
        == load_reference_program("accumulator_mixed_patterns.stim").rstrip()
    )


# -------------------------------------------------------------------------
# New tests: in-loop consumption of the accumulator. Each kernel uses
# in-loop indexing or slicing on `acc` (REPEAT-faithful patterns) plus a
# post-loop bare consumption to confirm both paths coexist.
#
# Faithful patterns:
#   - append shape (acc = acc + ms): negative indices acc[-j] for j in
#     [1, K], slice acc[-K:]
#   - prepend shape (acc = ms + acc): positive indices acc[i] for i in
#     [0, K-1], slice acc[:K]
# where K = len(ms) is the per-iteration delta size.
#
# Substring assertions used; reference .stim files can be added once the
# fix lands and the exact output is locked.
# -------------------------------------------------------------------------


def test_accumulator_append_empty_init_index_inside_loop_set_detector():
    """Append + empty init + acc[-1] inside loop + bare set_detector after.

    In-loop reference acc[-1] is this iteration's most-recent measurement,
    which is rec[-1] inside the REPEAT body for any iteration.
    Post-loop bare set_detector consumes all 6 measurements.
    """

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
            squin.set_detector([acc[-1]], coordinates=[0, 0])
        squin.set_detector(acc, coordinates=[1, 1])

    SquinToStimPass(dialects=test.dialects)(test)
    result = codegen(test)
    assert "REPEAT 3" in result
    assert "DETECTOR(0, 0) rec[-1]" in result
    assert "DETECTOR(1, 1) rec[-6] rec[-5] rec[-4] rec[-3] rec[-2] rec[-1]" in result


def test_accumulator_append_empty_init_slice_inside_loop_set_detector():
    """Append + empty init + acc[-2:] slice inside loop + bare set_detector after.

    In-loop slice acc[-2:] is this iteration's two measurements,
    rec[-2] rec[-1] inside the REPEAT body for any iteration.
    """

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
            squin.set_detector(acc[-2:], coordinates=[0, 0])
        squin.set_detector(acc, coordinates=[1, 1])

    SquinToStimPass(dialects=test.dialects)(test)
    result = codegen(test)
    assert "REPEAT 3" in result
    assert "DETECTOR(0, 0) rec[-2] rec[-1]" in result
    assert "DETECTOR(1, 1) rec[-6] rec[-5] rec[-4] rec[-3] rec[-2] rec[-1]" in result


def test_accumulator_append_initialized_index_inside_loop_set_observable():
    """Append + initialized + acc[-1] inside loop + bare set_observable after.

    Total measurements = 2 (init) + 3*2 = 8. In-loop and post-loop
    set_observable get distinct observable indices (0 and 1 respectively).
    """

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
            squin.set_observable([acc[-1]])
        squin.set_observable(acc)

    SquinToStimPass(dialects=test.dialects)(test)
    result = codegen(test)
    assert "REPEAT 3" in result
    assert "OBSERVABLE_INCLUDE(0) rec[-1]" in result
    assert (
        "OBSERVABLE_INCLUDE(1) rec[-8] rec[-7] rec[-6] rec[-5] "
        "rec[-4] rec[-3] rec[-2] rec[-1]" in result
    )


def test_accumulator_append_initialized_slice_inside_loop_set_observable():
    """Append + initialized + acc[-2:] slice inside loop + bare set_observable after."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
            squin.set_observable(acc[-2:])
        squin.set_observable(acc)

    SquinToStimPass(dialects=test.dialects)(test)
    result = codegen(test)
    assert "REPEAT 3" in result
    assert "OBSERVABLE_INCLUDE(0) rec[-2] rec[-1]" in result
    assert (
        "OBSERVABLE_INCLUDE(1) rec[-8] rec[-7] rec[-6] rec[-5] "
        "rec[-4] rec[-3] rec[-2] rec[-1]" in result
    )


def test_accumulator_prepend_empty_init_index_inside_loop_set_detector():
    """Prepend + empty init + acc[0] inside loop + bare set_detector after.

    For prepend (acc = ms + acc), acc[0] is this iteration's first
    fresh measurement, which sits at rec[-K] = rec[-2] inside the body.
    Post-loop bare consumption walks acc in prepend order: newest iter's
    measurements first.
    """

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
            squin.set_detector([acc[0]], coordinates=[0, 0])
        squin.set_detector(acc, coordinates=[1, 1])

    SquinToStimPass(dialects=test.dialects)(test)
    result = codegen(test)
    assert "REPEAT 3" in result
    assert "DETECTOR(0, 0) rec[-2]" in result
    assert "DETECTOR(1, 1) rec[-2] rec[-1] rec[-4] rec[-3] rec[-6] rec[-5]" in result


def test_accumulator_prepend_empty_init_slice_inside_loop_set_detector():
    """Prepend + empty init + acc[:2] slice inside loop + bare set_detector after.

    acc[:2] selects the first K=2 elements of acc, which after prepend
    contains exactly this iteration's measurements at the front,
    mapped to rec[-2] rec[-1].
    """

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
            squin.set_detector(acc[:2], coordinates=[0, 0])
        squin.set_detector(acc, coordinates=[1, 1])

    SquinToStimPass(dialects=test.dialects)(test)
    result = codegen(test)
    assert "REPEAT 3" in result
    assert "DETECTOR(0, 0) rec[-2] rec[-1]" in result
    assert "DETECTOR(1, 1) rec[-2] rec[-1] rec[-4] rec[-3] rec[-6] rec[-5]" in result


def test_accumulator_prepend_initialized_index_inside_loop_set_observable():
    """Prepend + initialized + acc[0] inside loop + bare set_observable after."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
            squin.set_observable([acc[0]])
        squin.set_observable(acc)

    SquinToStimPass(dialects=test.dialects)(test)
    result = codegen(test)
    assert "REPEAT 3" in result
    assert "OBSERVABLE_INCLUDE(0) rec[-2]" in result
    assert (
        "OBSERVABLE_INCLUDE(1) rec[-2] rec[-1] rec[-4] rec[-3] "
        "rec[-6] rec[-5] rec[-8] rec[-7]" in result
    )


def test_accumulator_prepend_initialized_slice_inside_loop_set_observable():
    """Prepend + initialized + acc[:2] slice inside loop + bare set_observable after."""

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
            squin.set_observable(acc[:2])
        squin.set_observable(acc)

    SquinToStimPass(dialects=test.dialects)(test)
    result = codegen(test)
    assert "REPEAT 3" in result
    assert "OBSERVABLE_INCLUDE(0) rec[-2] rec[-1]" in result
    assert (
        "OBSERVABLE_INCLUDE(1) rec[-2] rec[-1] rec[-4] rec[-3] "
        "rec[-6] rec[-5] rec[-8] rec[-7]" in result
    )
