from kirin.types import PyClass
from kirin.dialects import py, func

from bloqade import squin


def test_mult_rewrite():

    @squin.kernel
    def helper(x: squin.op.types.Op, y: squin.op.types.Op):
        return x * y

    @squin.kernel
    def main():
        q = squin.qubit.new(1)
        x = squin.op.x()
        y = squin.op.y()
        z = x * y
        t = helper(x, z)

        squin.qubit.apply(t, q)
        return q

    helper.print()
    main.print()

    assert isinstance(helper.code, func.Function)

    helper_stmts = list(helper.code.body.stmts())
    assert len(helper_stmts) == 2  # [Mult(), Return()]
    assert isinstance(helper_stmts[0], squin.op.stmts.Mult)

    assert isinstance(main.code, func.Function)

    count_mults_in_main = 0
    for stmt in main.code.body.stmts():
        assert not isinstance(stmt, py.Mult)

        count_mults_in_main += isinstance(stmt, squin.op.stmts.Mult)

    assert count_mults_in_main == 1


def test_scale_rewrite():

    @squin.kernel
    def simple_rmul():
        x = squin.op.x()
        y = 2 * x
        return y

    simple_rmul.print()

    assert isinstance(simple_rmul.code, func.Function)

    simple_rmul_stmts = list(simple_rmul.code.body.stmts())
    assert any(
        map(lambda stmt: isinstance(stmt, squin.op.stmts.Scale), simple_rmul_stmts)
    )
    assert not any(
        map(lambda stmt: isinstance(stmt, squin.op.stmts.Mult), simple_rmul_stmts)
    )
    assert not any(map(lambda stmt: isinstance(stmt, py.Mult), simple_rmul_stmts))

    @squin.kernel
    def simple_lmul():
        x = squin.op.x()
        y = x * 2
        return y

    simple_lmul.print()

    assert isinstance(simple_lmul.code, func.Function)

    simple_lmul_stmts = list(simple_lmul.code.body.stmts())
    assert any(
        map(lambda stmt: isinstance(stmt, squin.op.stmts.Scale), simple_lmul_stmts)
    )
    assert not any(
        map(lambda stmt: isinstance(stmt, squin.op.stmts.Mult), simple_lmul_stmts)
    )
    assert not any(map(lambda stmt: isinstance(stmt, py.Mult), simple_lmul_stmts))

    @squin.kernel
    def scale_mult():
        x = squin.op.x()
        y = squin.op.y()
        return 2 * (x * y)

    assert isinstance(scale_mult.code, func.Function)

    scale_mult_stmts = list(scale_mult.code.body.stmts())
    assert (
        sum(map(lambda stmt: isinstance(stmt, squin.op.stmts.Scale), scale_mult_stmts))
        == 1
    )
    assert (
        sum(map(lambda stmt: isinstance(stmt, squin.op.stmts.Mult), scale_mult_stmts))
        == 1
    )

    @squin.kernel
    def scale_mult2():
        x = squin.op.x()
        y = squin.op.y()
        return 2 * x * y

    scale_mult2.print()

    assert isinstance(scale_mult2.code, func.Function)

    scale_mult2_stmts = list(scale_mult2.code.body.stmts())
    assert (
        sum(map(lambda stmt: isinstance(stmt, squin.op.stmts.Scale), scale_mult2_stmts))
        == 1
    )
    assert (
        sum(map(lambda stmt: isinstance(stmt, squin.op.stmts.Mult), scale_mult2_stmts))
        == 1
    )


def test_scale_types():
    @squin.kernel
    def simple_lmul():
        x = squin.op.x()
        y = x * (2 + 0j)
        return y

    @squin.kernel
    def simple_rmul():
        x = squin.op.x()
        y = 2.1 * x
        return y

    @squin.kernel
    def nested_rmul():
        x = squin.op.x()
        y = squin.op.y()
        return 2 * x * y

    @squin.kernel
    def nested_rmul2():
        x = squin.op.x()
        y = squin.op.y()
        return 2 * (x * y)

    @squin.kernel
    def nested_lmul():
        x = squin.op.x()
        y = squin.op.y()
        return x * y * 2.0j

    def check_stmt_type(code, typ):
        for stmt in code.body.stmts():
            if isinstance(stmt, func.Return):
                continue
            is_op = stmt.result.type.is_subseteq(squin.op.types.OpType)
            is_num = stmt.result.type.is_equal(PyClass(typ))
            assert is_op or is_num

    check_stmt_type(simple_lmul.code, complex)
    check_stmt_type(simple_rmul.code, float)
    check_stmt_type(nested_rmul.code, int)
    check_stmt_type(nested_rmul2.code, int)
    check_stmt_type(nested_lmul.code, complex)
