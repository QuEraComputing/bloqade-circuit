from kirin import ir, types, rewrite
from kirin.dialects import cf, py

from bloqade.squin import wire
from bloqade.test_utils import assert_nodes
from bloqade.squin.rewrite.canonicalize import CanonicalizeWired


def test_canonicalize_wired_trivial():

    outer_region = ir.Region(test_block := ir.Block())

    inner_region = ir.Region(
        ir.Block([const := py.Constant(1), wire.Yield(const.result)])
    )

    test_block.stmts.append(const_zero := py.Constant(0))
    test_block.stmts.append(
        wired := wire.Wired(
            inner_region, memory_zone="test_zone", result_types=(types.Int,)
        ),
    )
    test_block.stmts.append(py.Add(wired.results[0], const_zero.result))

    expected_region = ir.Region(
        [
            parent_block := ir.Block(),
            inner_block := ir.Block(),
            exit_block := ir.Block(),
        ]
    )

    parent_block.stmts.append(const_zero := py.Constant(0))
    parent_block.stmts.append(
        cf.Branch(
            arguments=(),
            successor=inner_block,
        )
    )
    inner_block.stmts.append(
        const := py.Constant(1),
    )
    inner_block.stmts.append(
        cf.Branch(
            arguments=(const.result,),
            successor=exit_block,
        )
    )
    arg = exit_block.args.append_from(const.result.type)
    exit_block.stmts.append(py.Add(arg, const_zero.result))

    rewrite.Walk(CanonicalizeWired()).rewrite(outer_region)

    assert_nodes(outer_region, expected_region)


def test_hermitian_and_unitary():

    from bloqade import squin
    from bloqade.squin.analysis import hermitian_and_unitary

    @squin.kernel(fold=False)
    def main():
        n = 1
        x = squin.op.x()
        _ = n * x
        squin.op.control(x, n_controls=1)
        squin.op.pauli_string(string="XYZ")
        squin.op.pauli_string(string="XYX")

        squin.op.cx()

        y = squin.op.y()

        rx = squin.op.rot(axis=x, angle=0.125)
        _ = rx * squin.op.adjoint(rx)

        squin.op.rot(axis=y, angle=0)

    main.print()

    frame, _ = hermitian_and_unitary.HermitianAnalysis(main.dialects).run_analysis(
        main, no_raise=False
    )

    main.print(analysis=frame.entries)

    frame2, _ = hermitian_and_unitary.UnitaryAnalysis(main.dialects).run_analysis(
        main, no_raise=False
    )
    main.print(analysis=frame2.entries)
