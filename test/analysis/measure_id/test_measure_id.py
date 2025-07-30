from kirin.passes import HintConst
from kirin.dialects import scf

from bloqade.squin import op, qubit, kernel
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.analysis.measure_id.lattice import (
    NotMeasureId,
    MeasureIdBool,
    MeasureIdTuple,
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

    assert [frame.entries[result] for result in results_at(test, 0, 7)] == [
        NotMeasureId(),
        MeasureIdTuple((MeasureIdBool(idx=1),)),
    ]


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

    assert [frame.entries[result] for result in results_at(test, 0, 7)] == [
        NotMeasureId(),
        MeasureIdBool(idx=1),
    ]
