from bloqade import squin


def test_measure_register():
    @squin.kernel
    def test_measure_sugar():
        q = squin.qubit.new(2)

        return squin.qubit.measure(q)

    assert isinstance(
        test_measure_sugar.callable_region.blocks[-1].last_stmt, squin.qubit.MeasureReg
    )


def test_measure_qubit():
    @squin.kernel
    def test_measure_sugar():
        q = squin.qubit.new(2)

        return squin.qubit.measure(q[0])

    assert isinstance(
        test_measure_sugar.callable_region.blocks[-1].last_stmt,
        squin.qubit.MeasureQubit,
    )
