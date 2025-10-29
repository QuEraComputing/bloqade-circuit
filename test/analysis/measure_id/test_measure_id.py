from kirin.dialects import scf
from kirin.passes.inline import InlinePass

from bloqade import squin
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.stim.passes.flatten import Flatten
from bloqade.analysis.measure_id.lattice import (
    AnyMeasureId,
    NotMeasureId,
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

    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    measure_id_tuples = [
        value for value in frame.entries.values() if isinstance(value, MeasureIdTuple)
    ]

    # construct expected MeasureIdTuple
    expected_measure_id_tuple = MeasureIdTuple(
        data=tuple([MeasureIdBool(idx=i) for i in range(1, 11)])
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
    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    # Collect MeasureIdTuples
    measure_id_tuples = [
        value for value in frame.entries.values() if isinstance(value, MeasureIdTuple)
    ]

    # construct expected MeasureIdTuples
    measure_id_tuple_with_id_bools = MeasureIdTuple(
        data=tuple([MeasureIdBool(idx=i) for i in range(1, 6)])
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
    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

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
    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    # MeasureIdBool(idx=1) should occur twice:
    # First from the measurement in the true branch, then
    # the result of the scf.IfElse itself
    analysis_results = [
        val for val in frame.entries.values() if val == MeasureIdBool(idx=1)
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
    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)
    test.print(analysis=frame.entries)

    # MeasureIdBool(idx=1) should occur twice:
    # First from the measurement in the false branch, then
    # the result of the scf.IfElse itself
    analysis_results = [
        val for val in frame.entries.values() if val == MeasureIdBool(idx=1)
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

    InlinePass(test.dialects).fixpoint(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)
    # the result of the analysis on this Scf.IfElse should be two AnyMeasureIds.
    # One AnyMeasureId is from resolving the boolean type, which does not change
    # during any of the branches. The other is from the fact that broadcast.measure gives
    # an AnyMeasureId because it cannot figure out the concrete number of measurements, which has to be
    # joined against the MeasureIdBool from the other branch.
    assert list(frame.entries.values())[-2:] == [AnyMeasureId(), AnyMeasureId()]


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
    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    results = results_of_variables(test, ("msi", "msi2", "ms_final"))

    # This is an assertion against `msi` NOT the initial list of measurements
    assert frame.get(results["msi"]) == MeasureIdTuple(
        data=tuple(list(MeasureIdBool(idx=i) for i in range(2, 7)))
    )
    # msi2
    assert frame.get(results["msi2"]) == MeasureIdTuple(
        data=tuple(list(MeasureIdBool(idx=i) for i in range(3, 7)))
    )
    # ms_final
    assert frame.get(results["ms_final"]) == MeasureIdTuple(
        data=(MeasureIdBool(idx=3), MeasureIdBool(idx=5))
    )


def test_getitem_no_hint():
    @squin.kernel
    def test(idx):
        q = squin.qalloc(6)
        ms = squin.broadcast.measure(q)

        return ms[idx]

    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    assert [frame.entries[result] for result in results_at(test, 0, 3)] == [
        InvalidMeasureId(),
    ]


def test_getitem_invalid_hint():
    @squin.kernel
    def test():
        q = squin.qalloc(6)
        ms = squin.broadcast.measure(q)

        return ms["x"]

    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

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

    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    assert [frame.entries[result] for result in results_at(test, 0, 6)] == [
        InvalidMeasureId()
    ]
