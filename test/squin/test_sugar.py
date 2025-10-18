from kirin import ir
from kirin.dialects import func

from bloqade import squin


def get_return_value_stmt(kernel: ir.Method):
    assert isinstance(
        last_stmt := kernel.callable_region.blocks[-1].last_stmt, func.Return
    )
    return last_stmt.value.owner


def test_measure_register():
    @squin.kernel
    def test_measure_sugar():
        q = squin.qalloc(2)

        return squin.qubit.measure(q)

    assert isinstance(
        get_return_value_stmt(test_measure_sugar), squin.qubit.MeasureQubitList
    )


def test_measure_qubit():
    @squin.kernel
    def test_measure_sugar():
        q = squin.qalloc(2)

        return squin.qubit.measure(q[0])

    assert isinstance(
        get_return_value_stmt(test_measure_sugar),
        squin.qubit.MeasureQubit,
    )
