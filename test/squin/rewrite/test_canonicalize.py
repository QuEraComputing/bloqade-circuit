from kirin import ir, types, rewrite
from kirin.dialects import cf, py, func

from bloqade import squin
from bloqade.squin import wire
from bloqade.test_utils import assert_nodes
from bloqade.squin.analysis import unitary, hermitian
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

        squin.op.p0()
        squin.op.rot(axis=y, angle=0)

    main.print()

    hermitian_frame, _ = hermitian.HermitianAnalysis(main.dialects).run_analysis(
        main, no_raise=False
    )

    main.print(analysis=hermitian_frame.entries)

    unitary_frame, _ = unitary.UnitaryAnalysis(main.dialects).run_analysis(
        main, no_raise=False
    )
    main.print(analysis=unitary_frame.entries)

    def is_hermitian(stmt: squin.op.stmts.Operator | func.Invoke) -> bool:
        return hermitian_frame.get(stmt.result).is_equal(hermitian.Hermitian())

    def is_not_hermitian(stmt: squin.op.stmts.Operator) -> bool:
        return hermitian_frame.get(stmt.result).is_equal(hermitian.NotHermitian())

    def maybe_hermitian(stmt: squin.op.stmts.Operator) -> bool:
        return hermitian_frame.get(stmt.result).is_equal(hermitian.PossiblyHermitian())

    def is_unitary(stmt: squin.op.stmts.Operator | func.Invoke) -> bool:
        return unitary_frame.get(stmt.result).is_equal(unitary.Unitary())

    def is_not_unitary(stmt: squin.op.stmts.Operator) -> bool:
        return unitary_frame.get(stmt.result).is_equal(unitary.NotUnitary())

    for stmt in main.callable_region.blocks[0].stmts:
        match stmt:
            case squin.op.stmts.X() | squin.op.stmts.Y():
                assert is_hermitian(stmt)
                assert is_unitary(stmt)

            case squin.op.stmts.Scale():
                assert is_hermitian(stmt)
                assert is_unitary(stmt)
                assert stmt.is_hermitian
                assert stmt.is_unitary

            case squin.op.stmts.PauliString():
                assert is_unitary(stmt)
                assert is_hermitian(stmt)

            case func.Invoke():
                # NOTE: only cx above
                assert is_unitary(stmt)
                assert is_hermitian(stmt)

            case squin.op.stmts.Rot():
                assert is_unitary(stmt)
                assert maybe_hermitian(stmt)
                assert stmt.is_unitary

            case squin.op.stmts.Mult():
                assert is_unitary(stmt)
                assert is_not_hermitian(stmt)
                assert stmt.is_unitary
                assert not stmt.is_hermitian

            case squin.op.stmts.P0():
                assert is_hermitian(stmt)
                assert is_not_unitary(stmt)


test_hermitian_and_unitary()
