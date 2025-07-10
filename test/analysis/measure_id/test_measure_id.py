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


# Not sure why the measure_qubit_list impl doesn't get
# called considering the invoke impl does...
def test_invoke():

    @kernel
    # If I put an explicit type here it becomes AnyMeasureId
    # and it does touch the right impl but
    # the type attribute data is missing the list length
    def measure_generating_func(ql):
        return qubit.measure(ql)

    @kernel
    def test():
        ql = qubit.new(5)
        qubit.broadcast(op.x(), ql)
        return measure_generating_func(ql)

    frame, _ = MeasurementIDAnalysis(test.dialects).run_analysis(test)

    # measure_generating_func.print(analysis=frame.entries)

    test.print(analysis=frame.entries)
