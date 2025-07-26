# from kirin.types import AnyType
# from kirin.dialects.ilist import IList

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
