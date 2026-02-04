from kirin.passes.inline import InlinePass

from bloqade import squin, gemini
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.stim.passes.flatten import Flatten
from bloqade.analysis.measure_id.lattice import (
    Predicate,
    AnyMeasureId,
    NotMeasureId,
    RawMeasureId,
    MeasureIdTuple,
    InvalidMeasureId,
)


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

    # Test MeasureIdTuple with predicate
    data = tuple([RawMeasureId(idx=i) for i in range(-3, 0)])
    t0 = MeasureIdTuple(data=data, predicate=Predicate.IS_ONE)
    t1 = MeasureIdTuple(data=data, predicate=Predicate.IS_ONE)

    assert t0.is_subseteq(t1)

    t2 = MeasureIdTuple(data=data, predicate=Predicate.IS_ZERO)
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
        data=tuple([RawMeasureId(idx=i) for i in range(-10, 0)])
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
        data=tuple([RawMeasureId(idx=i) for i in range(-5, 0)])
    )
    measure_id_tuple_with_not_measures = MeasureIdTuple(
        data=tuple([NotMeasureId() for _ in range(5)])
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

    # MeasureIdBool(idx=1) should occur twice:
    # First from the measurement in the true branch, then
    # the result of the scf.IfElse itself
    analysis_results = [
        val for val in frame.entries.values() if val == RawMeasureId(idx=1)
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
        data=tuple(list(RawMeasureId(idx=i) for i in range(-5, 0)))
    )
    # msi2
    assert frame.get(results["msi2"]) == MeasureIdTuple(
        data=tuple(list(RawMeasureId(idx=i) for i in range(-4, 0)))
    )
    # ms_final
    assert frame.get(results["ms_final"]) == MeasureIdTuple(
        data=(RawMeasureId(idx=-4), RawMeasureId(idx=-2))
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

        is_zero_bools = squin.broadcast.is_zero(ms)
        is_one_bools = squin.broadcast.is_one(ms)
        is_lost_bools = squin.broadcast.is_lost(ms)

        return is_zero_bools, is_one_bools, is_lost_bools

    Flatten(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    results = results_of_variables(
        test, ("is_zero_bools", "is_one_bools", "is_lost_bools")
    )

    expected_is_zero_bools = MeasureIdTuple(
        data=tuple([RawMeasureId(idx=i) for i in range(-3, 0)]),
        predicate=Predicate.IS_ZERO,
    )

    expected_is_one_bools = MeasureIdTuple(
        data=tuple([RawMeasureId(idx=i) for i in range(-3, 0)]),
        predicate=Predicate.IS_ONE,
    )

    expected_is_lost_bools = MeasureIdTuple(
        data=tuple([RawMeasureId(idx=i) for i in range(-3, 0)]),
        predicate=Predicate.IS_LOST,
    )

    assert frame.get(results["is_zero_bools"]) == expected_is_zero_bools
    assert frame.get(results["is_one_bools"]) == expected_is_one_bools
    assert frame.get(results["is_lost_bools"]) == expected_is_lost_bools


def test_predicated_measure_alias():
    @squin.kernel
    def test():
        ql = squin.qalloc(3)
        ml = squin.broadcast.measure(ql)
        pred_ml = squin.broadcast.is_one(ml)
        pred_ml_alias = pred_ml  # alias on predicated measurement
        return pred_ml_alias

    Flatten(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    results = results_of_variables(test, ("pred_ml", "pred_ml_alias"))

    expected = MeasureIdTuple(
        data=tuple([RawMeasureId(idx=i) for i in range(-3, 0)]),
        predicate=Predicate.IS_ONE,
    )

    assert frame.get(results["pred_ml"]) == expected
    assert frame.get(results["pred_ml_alias"]) == expected


def test_terminal_logical_measurement():

    @gemini.logical.kernel(
        no_raise=False, typeinfer=True, aggressive_unroll=True, verify=False
    )
    def tm_logical_kernel():
        q = squin.qalloc(3)
        tm = gemini.logical.terminal_measure(q)
        return tm

    frame, _ = MeasurementIDAnalysis(tm_logical_kernel.dialects).run(tm_logical_kernel)
    # will have a MeasureIdTuple that's not from the terminal measurement,
    # basically a container of InvalidMeasureIds from the qubits that get allocated
    tm_logical_kernel.print(analysis=frame.entries)
    analysis_results = [
        val for val in frame.entries.values() if isinstance(val, MeasureIdTuple)
    ]
    expected_result = MeasureIdTuple(
        data=tuple([RawMeasureId(idx=-i) for i in range(1, 4)]),
        immutable=True,
    )
    assert expected_result in analysis_results


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
    # The IfElse result should be a properly joined MeasureIdTuple (immutable from set_detector)
    # Not AnyMeasureId since no measurements occur inside the branches
    analysis_results = [
        val
        for val in frame.entries.values()
        if isinstance(val, MeasureIdTuple) and val.immutable
    ]

    # Should have at least one immutable MeasureIdTuple from the joined detector results
    assert len(analysis_results) >= 1

    # The result should contain the correct measurement IDs (not AnyMeasureId)
    expected_detector_result = MeasureIdTuple(
        data=(
            RawMeasureId(idx=-3),
            RawMeasureId(idx=-2),
            RawMeasureId(idx=-1),
        ),
        immutable=True,
    )
    assert expected_detector_result in analysis_results


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

    # Check that immutable MeasureIdTuples from inside each branch exist in the frame
    immutable_tuples = [
        val
        for val in frame.entries.values()
        if isinstance(val, MeasureIdTuple) and val.immutable
    ]

    # d_1 should have measurements from ms1 (idx=-4, -3)
    expected_d_1 = MeasureIdTuple(
        data=(RawMeasureId(idx=-4), RawMeasureId(idx=-3)),
        immutable=True,
    )
    assert expected_d_1 in immutable_tuples

    # d_2 should have measurements from ms2 (idx=-2, -1)
    expected_d_2 = MeasureIdTuple(
        data=(RawMeasureId(idx=-2), RawMeasureId(idx=-1)),
        immutable=True,
    )
    assert expected_d_2 in immutable_tuples
