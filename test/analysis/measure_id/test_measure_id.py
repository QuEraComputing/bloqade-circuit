from kirin.passes import HintConst
from kirin.dialects import scf

from bloqade.squin import op, qubit, kernel
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.analysis.measure_id.lattice import (
    MeasureIdBool,
    MeasureIdTuple,
    InvalidMeasureId,
)


def results_at(kern, block_id, stmt_id):
    return kern.code.body.blocks[block_id].stmts.at(stmt_id).results  # type: ignore


def test_add():
    @kernel
    def test():

        ql1 = qubit.new(5)
        ql2 = qubit.new(5)
        qubit.broadcast(op.x(), ql1)
        qubit.broadcast(op.x(), ql2)
        ml1 = qubit.measure(ql1)
        ml2 = qubit.measure(ql2)
        return ml1 + ml2

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

    @kernel
    def test():
        ql = qubit.new(5)
        ml = qubit.measure(ql)
        ml_alias = ml

        return ml_alias

    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    test.print(analysis=frame.entries)

    # Collect MeasureIdTuples
    measure_id_tuples = [
        value for value in frame.entries.values() if isinstance(value, MeasureIdTuple)
    ]

    # construct expected MeasureIdTuple
    expected_measure_id_tuple = MeasureIdTuple(
        data=tuple([MeasureIdBool(idx=i) for i in range(1, 6)])
    )

    assert len(measure_id_tuples) == 2
    assert all(
        measure_id_tuple == expected_measure_id_tuple
        for measure_id_tuple in measure_id_tuples
    )


def test_measure_count_at_if_else():

    @kernel
    def test():
        q = qubit.new(5)
        qubit.apply(op.x(), q[2])
        ms = qubit.measure(q)

        if ms[1]:
            qubit.apply(op.x(), q[0])

        if ms[3]:
            qubit.apply(op.y(), q[1])

    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    assert all(
        isinstance(stmt, scf.IfElse) and measures_accumulated == 5
        for stmt, measures_accumulated in frame.num_measures_at_stmt.items()
    )


def test_scf_cond_true():
    @kernel
    def test():
        q = qubit.new(1)
        qubit.apply(op.x(), q[2])

        ms = None
        cond = True
        if cond:
            ms = qubit.measure(q)
        else:
            ms = qubit.measure(q[0])

        return ms

    HintConst(dialects=test.dialects).unsafe_run(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    # MeasureIdTuple(data=MeasureIdBool(idx=1),) should occur twice:
    # First from the measurement in the true branch, then
    # the result of the scf.IfElse itself
    analysis_results = [
        val
        for val in frame.entries.values()
        if val == MeasureIdTuple(data=(MeasureIdBool(idx=1),))
    ]
    assert len(analysis_results) == 2


def test_scf_cond_false():

    @kernel
    def test():
        q = qubit.new(5)
        qubit.apply(op.x(), q[2])

        ms = None
        cond = False
        if cond:
            ms = qubit.measure(q)
        else:
            ms = qubit.measure(q[0])

        return ms

    HintConst(dialects=test.dialects).unsafe_run(test)
    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    # MeasureIdBool(idx=1) should occur twice:
    # First from the measurement in the false branch, then
    # the result of the scf.IfElse itself
    analysis_results = [
        val for val in frame.entries.values() if val == MeasureIdBool(idx=1)
    ]
    assert len(analysis_results) == 2


def test_slice():
    @kernel
    def test():
        q = qubit.new(6)
        qubit.apply(op.x(), q[2])

        ms = qubit.measure(q)
        msi = ms[1:]  # MeasureIdTuple becomes a python tuple
        msi2 = msi[1:]  # slicing should still work on previous tuple
        ms_final = msi2[::2]

        return ms_final

    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    test.print(analysis=frame.entries)

    assert [frame.entries[result] for result in results_at(test, 0, 8)] == [
        MeasureIdTuple(data=tuple(list(MeasureIdBool(idx=i) for i in range(2, 7))))
    ]
    assert [frame.entries[result] for result in results_at(test, 0, 10)] == [
        MeasureIdTuple(data=tuple(list(MeasureIdBool(idx=i) for i in range(3, 7))))
    ]
    assert [frame.entries[result] for result in results_at(test, 0, 12)] == [
        MeasureIdTuple(data=(MeasureIdBool(idx=3), MeasureIdBool(idx=5)))
    ]


def test_getitem_no_hint():
    @kernel
    def test(idx):
        q = qubit.new(6)
        ms = qubit.measure(q)

        return ms[idx]

    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    assert [frame.entries[result] for result in results_at(test, 0, 3)] == [
        InvalidMeasureId(),
    ]


def test_getitem_invalid_hint():
    @kernel
    def test():
        q = qubit.new(6)
        ms = qubit.measure(q)

        return ms["x"]

    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    assert [frame.entries[result] for result in results_at(test, 0, 4)] == [
        InvalidMeasureId()
    ]


def test_getitem_propagate_invalid_measure():

    @kernel
    def test():
        q = qubit.new(6)
        ms = qubit.measure(q)
        # this will return an InvalidMeasureId
        invalid_ms = ms["x"]
        return invalid_ms[0]

    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    assert [frame.entries[result] for result in results_at(test, 0, 6)] == [
        InvalidMeasureId()
    ]
