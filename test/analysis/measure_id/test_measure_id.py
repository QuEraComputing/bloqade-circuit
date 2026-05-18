from kirin.dialects import scf, ilist
from kirin.passes.inline import InlinePass

from bloqade import squin
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.stim.passes.flatten import Flatten
from bloqade.analysis.measure_id.lattice import (
    Predicate,
    DetectorId,
    NotMeasureId,
    ObservableId,
    RawMeasureId,
    MeasureIdBool,
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


def test_subset_eq_MeasureIdBool():

    m0 = MeasureIdBool(idx=1, predicate=Predicate.IS_ONE)
    m1 = MeasureIdBool(idx=1, predicate=Predicate.IS_ONE)

    assert m0.is_subseteq(m1)

    # not equivalent if predicate is different
    m2 = MeasureIdBool(idx=1, predicate=Predicate.IS_ZERO)

    assert not m0.is_subseteq(m2)

    # not equivalent if index is different either,
    # they are only equivalent if both index and predicate match
    m3 = MeasureIdBool(idx=2, predicate=Predicate.IS_ONE)

    assert not m0.is_subseteq(m3)


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
        tuple([RawMeasureId(idx=i) for i in range(1, 11)]), ilist.IList
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
        tuple([RawMeasureId(idx=i) for i in range(1, 6)]), ilist.IList
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


def test_measure_count_at_if_else():

    @squin.kernel
    def test():
        q = squin.qalloc(5)
        squin.x(q[2])
        ms = squin.broadcast.measure(q)

        if ms[1]:
            squin.x(q[0])

        if ms[3]:
            squin.y(q[1])

    Flatten(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

    assert all(
        isinstance(stmt, scf.IfElse) and measures_accumulated == 5
        for stmt, measures_accumulated in frame.num_measures_at_stmt.items()
    )


def test_scf_cond_true():
    @squin.kernel
    def test():
        q = squin.qalloc(3)
        squin.x(q[2])

        ms = None
        cond = True
        if cond:
            ms = squin.measure(q[1])
        else:
            ms = squin.measure(q[0])

        return ms

    InlinePass(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

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

    # MeasureIdBool(idx=1) should occur twice:
    # First from the measurement in the false branch, then
    # the result of the scf.IfElse itself
    analysis_results = [
        val for val in frame.entries.values() if val == RawMeasureId(idx=1)
    ]
    assert len(analysis_results) == 2


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
    frame, _ = MeasurementIDAnalysis(test.dialects).run(test)
    analysis_results = [
        val for val in frame.entries.values() if isinstance(val, MeasureIdTuple)
    ]
    # Both branches of the scf.IfElse should be properly traversed and contain the following
    # analysis results.
    expected_full_register_measurement = MeasureIdTuple(
        tuple([RawMeasureId(idx=i) for i in range(1, 6)]), ilist.IList
    )
    expected_else_measurement = MeasureIdTuple((RawMeasureId(idx=6),), ilist.IList)
    assert expected_full_register_measurement in analysis_results
    assert expected_else_measurement in analysis_results


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
        tuple(list(RawMeasureId(idx=i) for i in range(2, 7))), ilist.IList
    )
    # msi2
    assert frame.get(results["msi2"]) == MeasureIdTuple(
        tuple(list(RawMeasureId(idx=i) for i in range(3, 7))), ilist.IList
    )
    # ms_final
    assert frame.get(results["ms_final"]) == MeasureIdTuple(
        (RawMeasureId(idx=3), RawMeasureId(idx=5)), ilist.IList
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
        tuple([MeasureIdBool(idx=i, predicate=Predicate.IS_ZERO) for i in range(1, 4)]),
        ilist.IList,
    )
    expected_is_one_bools = MeasureIdTuple(
        tuple([MeasureIdBool(idx=i, predicate=Predicate.IS_ONE) for i in range(1, 4)]),
        ilist.IList,
    )
    expected_is_lost_bools = MeasureIdTuple(
        tuple([MeasureIdBool(idx=i, predicate=Predicate.IS_LOST) for i in range(1, 4)]),
        ilist.IList,
    )

    assert frame.get(results["is_zero_bools"]) == expected_is_zero_bools
    assert frame.get(results["is_one_bools"]) == expected_is_one_bools
    assert frame.get(results["is_lost_bools"]) == expected_is_lost_bools


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
                0, MeasureIdTuple((RawMeasureId(1), RawMeasureId(2)), ilist.IList)
            ),
            DetectorId(
                1, MeasureIdTuple((RawMeasureId(5), RawMeasureId(6)), ilist.IList)
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

    assert result == MeasureIdTuple(
        (
            ObservableId(
                0, MeasureIdTuple((RawMeasureId(1), RawMeasureId(2)), ilist.IList)
            ),
            ObservableId(
                1, MeasureIdTuple((RawMeasureId(5), RawMeasureId(6)), ilist.IList)
            ),
        ),
        tuple,
    )
