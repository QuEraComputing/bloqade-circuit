from kirin.dialects import scf

from bloqade.squin import op, qubit, kernel
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.analysis.measure_id.lattice import MeasureIdBool, MeasureIdTuple


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
