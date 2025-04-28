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
