from kirin.dialects import ilist
from kirin.passes.inline import InlinePass

from bloqade import squin
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.stim.passes.flatten import Flatten
from bloqade.analysis.measure_id.lattice import (
    Predicate,
    DetectorId,
    AnyMeasureId,
    NotMeasureId,
    ObservableId,
    RawMeasureId,
    MeasureIdTuple,
    InvalidMeasureId,
)
from bloqade.stim.passes.flatten_except_loops import FlattenExceptLoops


def results_at(kern, block_id, stmt_id):
    return kern.code.body.blocks[block_id].stmts.at(stmt_id).results  # type: ignore


def results_of_variables(kernel, variable_names):
    results = {}
    for stmt in kernel.callable_region.stmts():
        for result in stmt.results:
            if result.name in variable_names:
                results[result.name] = result

    return results


def test_subset_eq_with_predicate():
    # Test RawMeasureId with predicate
    m0 = RawMeasureId(idx=1, predicate=Predicate.IS_ONE)
    m1 = RawMeasureId(idx=1, predicate=Predicate.IS_ONE)

    assert m0.is_subseteq(m1)

    # not equivalent if predicate is different
    m2 = RawMeasureId(idx=1, predicate=Predicate.IS_ZERO)

    assert not m0.is_subseteq(m2)

    # not equivalent if index is different either,
    # they are only equivalent if both index and predicate match
    m3 = RawMeasureId(idx=2, predicate=Predicate.IS_ONE)

    assert not m0.is_subseteq(m3)

    # Test MeasureIdTuple with predicated members
    data_with_pred = tuple(
        [RawMeasureId(idx=i, predicate=Predicate.IS_ONE) for i in range(-3, 0)]
    )
    t0 = MeasureIdTuple(data=data_with_pred)
    t1 = MeasureIdTuple(
        data=tuple(
            [RawMeasureId(idx=i, predicate=Predicate.IS_ONE) for i in range(-3, 0)]
        )
    )

    assert t0.is_subseteq(t1)

    t2 = MeasureIdTuple(
        data=tuple(
            [RawMeasureId(idx=i, predicate=Predicate.IS_ZERO) for i in range(-3, 0)]
        )
    )
    assert not t0.is_subseteq(t2)


def test_add():
    @squin.kernel
    def test():

        ql1 = squin.qalloc(5)
        ql2 = squin.qalloc(5)
        squin.broadcast.x(ql1)
        squin.broadcast.x(ql2)
        ml1 = squin.broadcast.measure(ql1)
        ml2 = squin.broadcast.measure(ql2)
        return ml1 + ml2

    Flatten(test.dialects).fixpoint(test)

    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    measure_id_tuples = [
        value for value in frame.entries.values() if isinstance(value, MeasureIdTuple)
    ]

    # construct expected MeasureIdTuple
    expected_measure_id_tuple = MeasureIdTuple(
        data=tuple([RawMeasureId(idx=i) for i in range(-10, 0)]),
        obj_type=ilist.IList,
    )

    assert measure_id_tuples[-1] == expected_measure_id_tuple


def test_measure_alias():

    @squin.kernel
    def test():
        ql = squin.qalloc(5)
        ml = squin.broadcast.measure(ql)
        ml_alias = ml

        return ml_alias

    Flatten(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    # Collect MeasureIdTuples
    measure_id_tuples = [
        value for value in frame.entries.values() if isinstance(value, MeasureIdTuple)
    ]

    # construct expected MeasureIdTuples
    measure_id_tuple_with_id_bools = MeasureIdTuple(
        data=tuple([RawMeasureId(idx=i) for i in range(-5, 0)]),
        obj_type=ilist.IList,
    )
    measure_id_tuple_with_not_measures = MeasureIdTuple(
        tuple([NotMeasureId() for _ in range(5)]), ilist.IList
    )

    assert len(measure_id_tuples) == 3
    # New qubit.new semantics cause a MeasureIdTuple to be generated full of NotMeasureIds because
    # qubit.new is actually an ilist.map that invokes single qubit allocation multiple times
    # and puts them into an ilist.
    assert measure_id_tuples[0] == measure_id_tuple_with_not_measures
    assert all(
        measure_id_tuple == measure_id_tuple_with_id_bools
        for measure_id_tuple in measure_id_tuples[1:]
    )


def scf_cond_true():
    @squin.kernel
    def test():
        q = squin.qalloc(3)
        squin.x(q[2])

        ms = None
        cond = True
        if cond:
            ms = squin.measure(q[1])  # need to enter the if-else
        else:
            ms = squin.measure(q[0])

        return ms

    InlinePass(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)
    test.print(analysis=frame.entries)

    # RawMeasureId(idx=-1) should occur twice:
    # First from the measurement in the true branch, then
    # the result of the scf.IfElse itself
    analysis_results = [
        val for val in frame.entries.values() if val == RawMeasureId(idx=-1)
    ]
    assert len(analysis_results) == 2


def test_scf_cond_false():

    @squin.kernel
    def test():
        q = squin.qalloc(5)
        squin.x(q[2])

        ms = None
        cond = False
        if cond:
            ms = squin.measure(q[1])
        else:
            ms = squin.measure(q[0])

        return ms

    # need to preserve the scf.IfElse but need things like qalloc to be inlined
    InlinePass(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)
    test.print(analysis=frame.entries)

    # Measurements inside branches cause the result to be AnyMeasureId (top element)
    analysis_results = [
        val for val in frame.entries.values() if isinstance(val, AnyMeasureId)
    ]
    assert len(analysis_results) >= 1


def test_scf_cond_unknown():

    @squin.kernel
    def test(cond: bool):
        q = squin.qalloc(5)
        squin.x(q[2])

        if cond:
            ms = squin.broadcast.measure(q)
        else:
            ms = squin.measure(q[0])

        return ms

    # We can use Flatten here because the variable condition for the scf.IfElse
    # means it cannot be simplified.
    Flatten(test.dialects).fixpoint(test)
    test.print()
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    # Both branches have measurements, so the IfElse results should be AnyMeasureId (top element)
    analysis_results = [
        val for val in frame.entries.values() if isinstance(val, AnyMeasureId)
    ]
    assert len(analysis_results) >= 1


def test_slice():
    @squin.kernel
    def test():
        q = squin.qalloc(6)
        squin.x(q[2])

        ms = squin.broadcast.measure(q)
        msi = ms[1:]  # MeasureIdTuple becomes a python tuple
        msi2 = msi[1:]  # slicing should still work on previous tuple
        ms_final = msi2[::2]

        return ms_final

    Flatten(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    results = results_of_variables(test, ("msi", "msi2", "ms_final"))

    # This is an assertion against `msi` NOT the initial list of measurements
    assert frame.get(results["msi"]) == MeasureIdTuple(
        data=tuple(list(RawMeasureId(idx=i) for i in range(-5, 0))),
        obj_type=ilist.IList,
    )
    # msi2
    assert frame.get(results["msi2"]) == MeasureIdTuple(
        data=tuple(list(RawMeasureId(idx=i) for i in range(-4, 0))),
        obj_type=ilist.IList,
    )
    # ms_final
    assert frame.get(results["ms_final"]) == MeasureIdTuple(
        data=(RawMeasureId(idx=-4), RawMeasureId(idx=-2)),
        obj_type=ilist.IList,
    )


def test_getitem_no_hint():
    @squin.kernel
    def test(idx):
        q = squin.qalloc(6)
        ms = squin.broadcast.measure(q)

        return ms[idx]

    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    assert [frame.entries[result] for result in results_at(test, 0, 3)] == [
        InvalidMeasureId(),
    ]


def test_getitem_invalid_hint():
    @squin.kernel
    def test():
        q = squin.qalloc(6)
        ms = squin.broadcast.measure(q)

        return ms["x"]

    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    assert [frame.entries[result] for result in results_at(test, 0, 4)] == [
        InvalidMeasureId()
    ]


def test_getitem_propagate_invalid_measure():

    @squin.kernel
    def test():
        q = squin.qalloc(6)
        ms = squin.broadcast.measure(q)
        # this will return an InvalidMeasureId
        invalid_ms = ms["x"]
        return invalid_ms[0]

    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    assert [frame.entries[result] for result in results_at(test, 0, 6)] == [
        InvalidMeasureId()
    ]


def test_measurement_predicates():
    @squin.kernel
    def test():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)

        m_is_zero = squin.broadcast.is_zero(ms)
        m_is_one = squin.broadcast.is_one(ms)
        m_is_lost = squin.broadcast.is_lost(ms)

        return m_is_zero, m_is_one, m_is_lost

    Flatten(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    results = results_of_variables(test, ("m_is_zero", "m_is_one", "m_is_lost"))

    expected_m_is_zero = MeasureIdTuple(
        data=tuple(
            [RawMeasureId(idx=i, predicate=Predicate.IS_ZERO) for i in range(-3, 0)]
        ),
        obj_type=ilist.IList,
    )

    expected_m_is_one = MeasureIdTuple(
        data=tuple(
            [RawMeasureId(idx=i, predicate=Predicate.IS_ONE) for i in range(-3, 0)]
        ),
        obj_type=ilist.IList,
    )

    expected_m_is_lost = MeasureIdTuple(
        data=tuple(
            [RawMeasureId(idx=i, predicate=Predicate.IS_LOST) for i in range(-3, 0)]
        ),
        obj_type=ilist.IList,
    )

    assert frame.get(results["m_is_zero"]) == expected_m_is_zero
    assert frame.get(results["m_is_one"]) == expected_m_is_one
    assert frame.get(results["m_is_lost"]) == expected_m_is_lost


def test_predicated_measure_alias():
    @squin.kernel
    def test():
        ql = squin.qalloc(3)
        ml = squin.broadcast.measure(ql)
        m_is_one = squin.broadcast.is_one(ml)
        m_is_one_alias = m_is_one  # alias on predicated measurement
        return m_is_one_alias

    Flatten(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    results = results_of_variables(test, ("m_is_one", "m_is_one_alias"))

    expected = MeasureIdTuple(
        data=tuple(
            [RawMeasureId(idx=i, predicate=Predicate.IS_ONE) for i in range(-3, 0)]
        ),
        obj_type=ilist.IList,
    )

    assert frame.get(results["m_is_one"]) == expected
    assert frame.get(results["m_is_one_alias"]) == expected


def test_mixed_predicates():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        ms = squin.broadcast.measure(q)

        m_is_zero = squin.is_zero(ms[0])
        m_is_one = squin.is_one(ms[1])

        result = (m_is_zero, m_is_one)
        return result

    Flatten(test.dialects).fixpoint(test)
    frame, result = MeasurementIDAnalysis(test.dialects).run(test)

    # Result should be a tuple with two RawMeasureIds having different predicates
    assert result == MeasureIdTuple(
        (
            RawMeasureId(idx=-2, predicate=Predicate.IS_ZERO),
            RawMeasureId(idx=-1, predicate=Predicate.IS_ONE),
        ),
        tuple,
    )


def test_detectors():
    @squin.kernel
    def test():
        q = squin.qalloc(4)
        m0 = squin.broadcast.measure(q)
        d0 = squin.set_detector([m0[0], m0[1]], coordinates=[0, 0])
        m1 = squin.broadcast.measure(q)
        d1 = squin.set_detector([m1[0], m1[1]], coordinates=[1, 1])
        return d0, d1

    Flatten(test.dialects).fixpoint(test)
    _, result = MeasurementIDAnalysis(test.dialects).run(test)

    assert result == MeasureIdTuple(
        (
            DetectorId(
                0,
                MeasureIdTuple((RawMeasureId(-4), RawMeasureId(-3)), ilist.IList),
                coordinates=(0, 0),
            ),
            DetectorId(
                1,
                MeasureIdTuple((RawMeasureId(-4), RawMeasureId(-3)), ilist.IList),
                coordinates=(1, 1),
            ),
        ),
        tuple,
    )


def test_observables():
    @squin.kernel
    def test():
        q = squin.qalloc(4)
        m0 = squin.broadcast.measure(q)
        o0 = squin.set_observable([m0[0], m0[1]], 0)
        m1 = squin.broadcast.measure(q)
        o1 = squin.set_observable([m1[0], m1[1]], 1)
        return o0, o1

    Flatten(test.dialects).fixpoint(test)
    _, result = MeasurementIDAnalysis(test.dialects).run(test)
    print(result)

    assert result == MeasureIdTuple(
        (
            ObservableId(
                0, MeasureIdTuple((RawMeasureId(-4), RawMeasureId(-3)), ilist.IList)
            ),
            ObservableId(
                1, MeasureIdTuple((RawMeasureId(-4), RawMeasureId(-3)), ilist.IList)
            ),
        ),
        tuple,
    )


test_observables()


def test_detector_in_both_branches():
    @squin.kernel
    def test(cond: bool):
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)

        # Define detectors in both branches using measurements from before the if-else
        if cond:
            d = squin.set_detector(ms, [0.0, 0.0])
        else:
            d = squin.set_detector(ms, [1.0, 1.0])

        return d

    Flatten(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)
    test.print(analysis=frame.entries)

    # Both branches define detectors using the same measurements
    # The IfElse result should be a properly joined DetectorId
    # Not AnyMeasureId since no measurements occur inside the branches
    detector_results = [
        val for val in frame.entries.values() if isinstance(val, DetectorId)
    ]

    # Should have DetectorIds from each branch
    assert len(detector_results) >= 1

    # The DetectorIds should contain the correct measurement IDs with negative indices
    expected_type = MeasureIdTuple(
        data=(
            RawMeasureId(idx=-3),
            RawMeasureId(idx=-2),
            RawMeasureId(idx=-1),
        ),
        obj_type=ilist.IList,
    )
    # Check that at least one DetectorId has the expected data
    assert any(d.data == expected_type for d in detector_results)


def test_detector_in_both_branches_different_measurements():
    @squin.kernel
    def test(cond: bool):
        q1 = squin.qalloc(2)
        q2 = squin.qalloc(2)
        ms1 = squin.broadcast.measure(q1)
        ms2 = squin.broadcast.measure(q2)

        # Define detectors in both branches using DIFFERENT measurements
        if cond:
            d = squin.set_detector(ms1, [0.0, 0.0])
        else:
            d = squin.set_detector(ms2, [1.0, 1.0])

        return d

    Flatten(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)
    test.print(analysis=frame.entries)

    # Both branches define detectors using different measurements
    # The joined result should be AnyMeasureId (top) because the measurement sets differ
    # Check that the IfElse result is AnyMeasureId
    any_measure_id_results = [
        val for val in frame.entries.values() if isinstance(val, AnyMeasureId)
    ]
    assert len(any_measure_id_results) >= 1

    # Check that DetectorIds from inside each branch exist in the frame
    detector_results = [
        val for val in frame.entries.values() if isinstance(val, DetectorId)
    ]

    # d_1 should have measurements from ms1 (idx=-4, -3)
    expected_then_detector_type = MeasureIdTuple(
        data=(RawMeasureId(idx=-4), RawMeasureId(idx=-3)),
        obj_type=ilist.IList,
    )
    assert any(d.data == expected_then_detector_type for d in detector_results)

    # d_2 should have measurements from ms2 (idx=-2, -1)
    expected_else_detector_type = MeasureIdTuple(
        data=(RawMeasureId(idx=-2), RawMeasureId(idx=-1)),
        obj_type=ilist.IList,
    )
    assert any(d.data == expected_else_detector_type for d in detector_results)


def test_detector_coordinate_forwarding_mixed():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        ms = squin.broadcast.measure(q)
        d = squin.set_detector([ms[0], ms[1]], coordinates=[1.5, 2.0, 3])
        return d

    Flatten(test.dialects).fixpoint(test)
    _, result = MeasurementIDAnalysis(test.dialects).run(test)

    assert result == DetectorId(
        0,
        MeasureIdTuple((RawMeasureId(-2), RawMeasureId(-1)), ilist.IList),
        coordinates=(1.5, 2.0, 3),
    )


def test_detector_coordinate_forwarding_from_indexing():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        ms = squin.broadcast.measure(q)
        nums = [10, 20, 30]
        t = (4.0, 5.0)
        d = squin.set_detector([ms[0], ms[1]], coordinates=[nums[2], t[0]])
        return d

    Flatten(test.dialects).fixpoint(test)
    _, result = MeasurementIDAnalysis(test.dialects).run(test)

    assert result == DetectorId(
        0,
        MeasureIdTuple((RawMeasureId(-2), RawMeasureId(-1)), ilist.IList),
        coordinates=(30, 4.0),
    )


def test_detector_coordinate_forwarding_from_slicing():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        ms = squin.broadcast.measure(q)
        nums = [10, 20, 30, 40]
        list_sliced = nums[1:3]
        t = (1.0, 2.0, 3.0, 4.0)
        tuple_sliced = t[::2]
        d = squin.set_detector(
            [ms[0], ms[1]], coordinates=[list_sliced[0], tuple_sliced[1]]
        )
        return d

    Flatten(test.dialects).fixpoint(test)
    _, result = MeasurementIDAnalysis(test.dialects).run(test)

    assert result == DetectorId(
        0,
        MeasureIdTuple((RawMeasureId(-2), RawMeasureId(-1)), ilist.IList),
        coordinates=(20, 3.0),
    )


def test_detector_coordinate_forwarding_with_interleaved_measurement():
    @squin.kernel
    def test():
        q = squin.qalloc(3)
        m0 = squin.broadcast.measure(q)
        nums = [10, 20, 30, 40]
        list_sliced = nums[1:3]
        t = (1.0, 2.0, 3.0, 4.0)
        tuple_sliced = t[::2]
        d0 = squin.set_detector(
            [m0[0], m0[1]], coordinates=[list_sliced[0], tuple_sliced[1]]
        )
        m1 = squin.broadcast.measure(q)
        d1 = squin.set_detector(
            [m1[1], m1[2]], coordinates=[tuple_sliced[0], list_sliced[1]]
        )
        return d0, d1

    Flatten(test.dialects).fixpoint(test)
    _, result = MeasurementIDAnalysis(test.dialects).run(test)

    assert result == MeasureIdTuple(
        (
            DetectorId(
                0,
                MeasureIdTuple((RawMeasureId(-3), RawMeasureId(-2)), ilist.IList),
                coordinates=(20, 3.0),
            ),
            DetectorId(
                1,
                MeasureIdTuple((RawMeasureId(-2), RawMeasureId(-1)), ilist.IList),
                coordinates=(1.0, 30),
            ),
        ),
        tuple,
    )


def test_accumulator_append_empty_init():

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(squin.qalloc(0))
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        return acc

    FlattenExceptLoops(test.dialects).fixpoint(test)
    _, result = MeasurementIDAnalysis(test.dialects).run(test)

    expected = MeasureIdTuple(
        data=tuple(RawMeasureId(idx=i) for i in range(-6, 0)),
        obj_type=ilist.IList,
    )
    assert result == expected


def test_accumulator_prepend_empty_init():

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(squin.qalloc(0))
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        return acc

    FlattenExceptLoops(test.dialects).fixpoint(test)
    _, result = MeasurementIDAnalysis(test.dialects).run(test)

    # Prepend: newest chunk first, oldest chunk last.
    # iter 3 (newest): (-2, -1), iter 2: (-4, -3), iter 1 (oldest): (-6, -5)
    expected = MeasureIdTuple(
        data=(
            RawMeasureId(idx=-2),
            RawMeasureId(idx=-1),
            RawMeasureId(idx=-4),
            RawMeasureId(idx=-3),
            RawMeasureId(idx=-6),
            RawMeasureId(idx=-5),
        ),
        obj_type=ilist.IList,
    )
    assert result == expected


def test_accumulator_append_initialized():

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
        return acc

    FlattenExceptLoops(test.dialects).fixpoint(test)
    _, result = MeasurementIDAnalysis(test.dialects).run(test)

    # init: 2 measurements, 3 iters x 2 = 6 new, total 8
    # init shifted by -6: (-8, -7)
    # new monotonic: (-6, -5, -4, -3, -2, -1)
    # append: init + new = (-8, -7, -6, -5, -4, -3, -2, -1)
    expected = MeasureIdTuple(
        data=tuple(RawMeasureId(idx=i) for i in range(-8, 0)),
        obj_type=ilist.IList,
    )
    assert result == expected


def test_accumulator_prepend_initialized():

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = squin.broadcast.measure(qs)
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = ms + acc
        return acc

    FlattenExceptLoops(test.dialects).fixpoint(test)
    _, result = MeasurementIDAnalysis(test.dialects).run(test)

    # init: 2 measurements shifted by -6 total: (-8, -7)
    # Prepend: newest chunk first, oldest chunk last, then init
    # iter 3 (newest): (-2, -1), iter 2: (-4, -3), iter 1 (oldest): (-6, -5)
    # final: (-2, -1, -4, -3, -6, -5, -8, -7)
    expected = MeasureIdTuple(
        data=(
            RawMeasureId(idx=-2),
            RawMeasureId(idx=-1),
            RawMeasureId(idx=-4),
            RawMeasureId(idx=-3),
            RawMeasureId(idx=-6),
            RawMeasureId(idx=-5),
            RawMeasureId(idx=-8),
            RawMeasureId(idx=-7),
        ),
        obj_type=ilist.IList,
    )
    assert result == expected


def test_detector_in_loop_with_invariant_accumulator_access():

    # Negative indexing with appended measurements to the accumulation list
    # should be guaranteed to work with invariance check infrastructure

    @squin.kernel
    def test():
        qs = squin.qalloc(2)
        acc = []
        for _ in range(3):
            ms = squin.broadcast.measure(qs)
            acc = acc + ms
            squin.set_detector([acc[-1], acc[-2]], coordinates=[0, 0])
        return acc

    FlattenExceptLoops(test.dialects).fixpoint(test)
    frame, result = MeasurementIDAnalysis(test.dialects).run(test)

    expected_acc = MeasureIdTuple(
        data=tuple(RawMeasureId(idx=i) for i in range(-6, 0)),
        obj_type=ilist.IList,
    )
    assert result == expected_acc

    detector_results = [
        val for val in frame.entries.values() if isinstance(val, DetectorId)
    ]
    assert len(detector_results) == 1

    expected_detector = DetectorId(
        idx=0,
        data=MeasureIdTuple(
            data=(RawMeasureId(idx=-1), RawMeasureId(idx=-2)),
            obj_type=ilist.IList,
        ),
        coordinates=(0, 0),
    )
    assert detector_results[0] == expected_detector
