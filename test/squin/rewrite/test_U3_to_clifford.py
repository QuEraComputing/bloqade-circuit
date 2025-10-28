import math

from kirin import ir
from kirin.rewrite import Walk, Chain
from kirin.passes.abc import Pass
from kirin.rewrite.dce import DeadCodeElimination

from bloqade import squin as sq
from bloqade.squin import gate
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.squin.rewrite.U3_to_clifford import SquinU3ToClifford


class SquinToCliffordTestPass(Pass):

    def unsafe_run(self, mt: ir.Method):

        rewrite_result = AggressiveUnroll(mt.dialects).fixpoint(mt)

        print("after unroll")
        mt.print()

        return (
            Walk(Chain(Walk(SquinU3ToClifford()), Walk(DeadCodeElimination())))
            .rewrite(mt.code)
            .join(rewrite_result)
        )


def get_stmt_at_idx(method: ir.Method, idx: int) -> ir.Statement:
    return method.callable_region.blocks[0].stmts.at(idx)


def filter_statements_by_type(
    method: ir.Method, types: tuple[type, ...]
) -> list[ir.Statement]:
    return [
        stmt
        for stmt in method.callable_region.blocks[0].stmts
        if isinstance(stmt, types)
    ]


def test_identity():

    @sq.kernel
    def test():

        q = sq.qalloc(4)
        sq.u3(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    # Should be no U3 statements left, they are eliminated if they're equivalent to Identity
    no_stmt = filter_statements_by_type(test, (gate.stmts.U3,))
    assert len(no_stmt) == 0


def test_s():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # S gate
        sq.u3(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=0.25 * math.tau, qubit=q[0])
        # Equivalent S gate (different parameters)
        sq.u3(theta=math.tau, phi=0.5 * math.tau, lam=0.75 * math.tau, qubit=q[1])
        # S gate alternative form
        sq.u3(theta=0.0, phi=0.25 * math.tau, lam=0.0, qubit=q[2])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 7), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 9), gate.stmts.S)
    S_stmts = filter_statements_by_type(test, (gate.stmts.S,))
    # Should be normal S gates, not adjoint/dagger
    assert not S_stmts[0].adjoint
    assert not S_stmts[1].adjoint
    assert not S_stmts[2].adjoint


def test_z():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # nice positive representation
        sq.u3(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=0.5 * math.tau, qubit=q[0])
        # wrap around
        sq.u3(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=1.5 * math.tau, qubit=q[1])
        # go backwards
        sq.u3(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=-0.5 * math.tau, qubit=q[2])
        # alternative form
        sq.u3(theta=0.0, phi=0.5 * math.tau, lam=0.0, qubit=q[3])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 7), gate.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 9), gate.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 11), gate.stmts.Z)


def test_sdag():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        sq.u3(
            theta=0.0 * math.tau, phi=0.0 * math.tau, lam=-0.25 * math.tau, qubit=q[0]
        )
        sq.u3(theta=0.0 * math.tau, phi=0.5 * math.tau, lam=0.25 * math.tau, qubit=q[1])
        sq.u3(theta=0.0, phi=-0.25 * math.tau, lam=0.0, qubit=q[2])
        sq.u3(theta=0.0, phi=0.75 * math.tau, lam=0.0, qubit=q[3])
        sq.u3(theta=2 * math.tau, phi=0.7 * math.tau, lam=0.05 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    test.print()

    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 7), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 9), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 11), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 12), gate.stmts.S)

    sdag_stmts = filter_statements_by_type(test, (gate.stmts.S,))
    for sdag_stmt in sdag_stmts:
        assert sdag_stmt.adjoint


# Checks that Sdag is the first gate that gets generated,
# There is a Y that gets appended afterwards but is not checked
def test_sdag_weirder_case():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        sq.u3(theta=0.5 * math.tau, phi=0.05 * math.tau, lam=0.8 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.S)
    [S_stmt] = filter_statements_by_type(test, (gate.stmts.S,))
    assert S_stmt.adjoint


def test_sqrt_y():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # equivalent to sqrt(y) gate
        sq.u3(theta=0.25 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau, qubit=q[0])
        sq.u3(theta=1.25 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)

    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 6), gate.stmts.SqrtY)
    sqrt_y_stmts = filter_statements_by_type(test, (gate.stmts.SqrtY,))
    assert not sqrt_y_stmts[0].adjoint
    assert not sqrt_y_stmts[1].adjoint


def test_s_sqrt_y():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        sq.u3(
            theta=0.25 * math.tau, phi=0.0 * math.tau, lam=0.25 * math.tau, qubit=q[0]
        )
        sq.u3(
            theta=1.25 * math.tau, phi=1.0 * math.tau, lam=1.25 * math.tau, qubit=q[1]
        )

    SquinToCliffordTestPass(test.dialects)(test)

    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 6), gate.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 8), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 9), gate.stmts.SqrtY)

    s_stmts = filter_statements_by_type(test, (gate.stmts.S,))
    sqrt_y_stmts = filter_statements_by_type(test, (gate.stmts.SqrtY,))

    for s_stmt in s_stmts:
        assert not s_stmt.adjoint

    for sqrt_y_stmt in sqrt_y_stmts:
        assert not sqrt_y_stmt.adjoint


def test_h():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 0, 1)
        sq.u3(theta=0.25 * math.tau, phi=0.0 * math.tau, lam=0.5 * math.tau, qubit=q[0])
        sq.u3(theta=1.25 * math.tau, phi=0.0 * math.tau, lam=1.5 * math.tau, qubit=q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.H)
    assert isinstance(get_stmt_at_idx(test, 7), gate.stmts.H)


def test_sdg_sqrt_y():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 0, 3)
        sq.u3(
            theta=0.25 * math.tau, phi=0.0 * math.tau, lam=0.75 * math.tau, qubit=q[0]
        )
        sq.u3(
            theta=-1.75 * math.tau, phi=0.0 * math.tau, lam=-1.25 * math.tau, qubit=q[1]
        )

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 6), gate.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 8), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 9), gate.stmts.SqrtY)

    s_stmts = filter_statements_by_type(test, (gate.stmts.S,))
    sqrt_y_stmts = filter_statements_by_type(test, (gate.stmts.SqrtY,))

    for s_stmt in s_stmts:
        assert s_stmt.adjoint

    for sqrt_y_stmt in sqrt_y_stmts:
        assert not sqrt_y_stmt.adjoint


def test_s_sqrt_x_dag():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 1, 0)
        sq.u3(
            theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.0 * math.tau, qubit=q[0]
        )
        sq.u3(
            theta=1.25 * math.tau, phi=-1.75 * math.tau, lam=0.0 * math.tau, qubit=q[1]
        )

    SquinToCliffordTestPass(test.dialects)(test)
    test.print()
    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 6), gate.stmts.SqrtX)
    assert isinstance(get_stmt_at_idx(test, 8), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 9), gate.stmts.SqrtX)

    sqrt_x_stmts = filter_statements_by_type(test, (gate.stmts.SqrtX,))
    s_stmts = filter_statements_by_type(test, (gate.stmts.S,))

    for sqrt_x_stmt in sqrt_x_stmts:
        assert sqrt_x_stmt.adjoint

    for s_stmt in s_stmts:
        assert not s_stmt.adjoint


def test_z_sqrt_x_dag():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 1, 1)
        sq.u3(
            theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.25 * math.tau, qubit=q[0]
        )
        sq.u3(
            theta=1.25 * math.tau, phi=1.25 * math.tau, lam=1.25 * math.tau, qubit=q[1]
        )

    SquinToCliffordTestPass(test.dialects)(test)

    s_stmts = filter_statements_by_type(test, (gate.stmts.S,))
    sqrt_x_stmts = filter_statements_by_type(test, (gate.stmts.SqrtX,))

    assert [
        type(stmt)
        for stmt in filter_statements_by_type(
            test, (gate.stmts.S, gate.stmts.Z, gate.stmts.SqrtX, gate.stmts.SqrtY)
        )
    ] == [
        gate.stmts.Z,
        gate.stmts.SqrtX,
        gate.stmts.Z,
        gate.stmts.SqrtX,
    ]

    # Check adjoint property
    for s_stmt in s_stmts:
        assert not s_stmt.adjoint
    for sqrt_x_stmt in sqrt_x_stmts:
        assert sqrt_x_stmt.adjoint


def test_s_dag_sqrt_x_dag():

    @sq.kernel
    def test():
        q = sq.qalloc(1)
        # (1, 1, 2)
        sq.u3(
            theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.5 * math.tau, qubit=q[0]
        )
        sq.u3(
            theta=1.25 * math.tau, phi=1.25 * math.tau, lam=1.5 * math.tau, qubit=q[0]
        )

    SquinToCliffordTestPass(test.dialects)(test)
    test.print()

    relevant_stmts = filter_statements_by_type(
        test, (gate.stmts.Z, gate.stmts.SqrtY, gate.stmts.S, gate.stmts.SqrtX)
    )

    expected_types = [
        gate.stmts.S,
        gate.stmts.SqrtX,
        gate.stmts.S,
        gate.stmts.SqrtX,
    ]
    assert [type(stmt) for stmt in relevant_stmts] == expected_types

    for relevant_stmt in relevant_stmts:
        if type(relevant_stmt) is not gate.stmts.Z:
            assert relevant_stmt.adjoint


def test_sqrt_x_dag():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 1, 3)
        sq.u3(
            theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.75 * math.tau, qubit=q[0]
        )
        sq.u3(
            theta=1.25 * math.tau, phi=1.25 * math.tau, lam=1.75 * math.tau, qubit=q[1]
        )

    SquinToCliffordTestPass(test.dialects)(test)

    relevant_stmts = filter_statements_by_type(
        test, (gate.stmts.S, gate.stmts.SqrtY, gate.stmts.SqrtX)
    )

    assert [type(stmt) for stmt in relevant_stmts] == [
        gate.stmts.SqrtX,
        gate.stmts.SqrtX,
    ]

    s_stmts = filter_statements_by_type(test, (gate.stmts.S,))
    sqrt_x_stmts = filter_statements_by_type(test, (gate.stmts.SqrtX,))

    assert not s_stmts
    for sqrt_x_stmt in sqrt_x_stmts:
        assert sqrt_x_stmt.adjoint


def test_z_sqrt_y_dag():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 2, 0)
        sq.u3(theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.0 * math.tau, qubit=q[0])
        sq.u3(
            theta=1.25 * math.tau, phi=-1.5 * math.tau, lam=0.0 * math.tau, qubit=q[1]
        )

    SquinToCliffordTestPass(test.dialects)(test)
    test.print()

    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 6), gate.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 8), gate.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 9), gate.stmts.SqrtY)

    sqrt_y_stmts = filter_statements_by_type(test, (gate.stmts.SqrtY,))
    for sqrt_y_stmt in sqrt_y_stmts:
        assert sqrt_y_stmt.adjoint


def test_s_dag_sqrt_y_dag():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 2, 1)
        sq.u3(
            theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.25 * math.tau, qubit=q[0]
        )
        sq.u3(
            theta=1.25 * math.tau, phi=1.5 * math.tau, lam=-1.75 * math.tau, qubit=q[1]
        )

    SquinToCliffordTestPass(test.dialects)(test)

    relevant_stmts = filter_statements_by_type(
        test, (gate.stmts.S, gate.stmts.SqrtY, gate.stmts.Z)
    )

    assert [type(stmt) for stmt in relevant_stmts] == [
        gate.stmts.S,
        gate.stmts.SqrtY,
        gate.stmts.S,
        gate.stmts.SqrtY,
    ]

    for stmt in relevant_stmts:
        if type(stmt) is not gate.stmts.Z:
            assert stmt.adjoint


def test_sqrt_y_dag():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 2, 2)
        sq.u3(theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.5 * math.tau, qubit=q[0])
        sq.u3(
            theta=1.25 * math.tau, phi=-0.5 * math.tau, lam=-1.5 * math.tau, qubit=q[1]
        )

    SquinToCliffordTestPass(test.dialects)(test)

    relevant_stmts = filter_statements_by_type(test, (gate.stmts.Z, gate.stmts.SqrtY))

    expected_types = [
        gate.stmts.SqrtY,
        gate.stmts.SqrtY,
    ]
    assert [type(stmt) for stmt in relevant_stmts] == expected_types

    for stmt in relevant_stmts:
        if type(stmt) is gate.stmts.SqrtY:
            assert stmt.adjoint


def test_s_sqrt_y_dag():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 2, 3)
        sq.u3(
            theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.75 * math.tau, qubit=q[0]
        )
        sq.u3(
            theta=1.25 * math.tau, phi=1.5 * math.tau, lam=-1.25 * math.tau, qubit=q[1]
        )

    SquinToCliffordTestPass(test.dialects)(test)

    relevant_stmts = filter_statements_by_type(
        test, (gate.stmts.S, gate.stmts.SqrtY, gate.stmts.Z)
    )

    assert [type(stmt) for stmt in relevant_stmts] == [
        gate.stmts.S,
        gate.stmts.SqrtY,
        gate.stmts.S,
        gate.stmts.SqrtY,
    ]

    s_stmts = filter_statements_by_type(test, (gate.stmts.S,))
    sqrt_y_stmts = filter_statements_by_type(test, (gate.stmts.SqrtY,))

    for s_stmt in s_stmts:
        assert not s_stmt.adjoint

    for sqrt_y_stmt in sqrt_y_stmts:
        assert sqrt_y_stmt.adjoint


def test_s_dag_sqrt_x():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 3, 0)
        sq.u3(
            theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.0 * math.tau, qubit=q[0]
        )

    SquinToCliffordTestPass(test.dialects)(test)

    relevant_stmts = filter_statements_by_type(
        test, (gate.stmts.SqrtY, gate.stmts.SqrtX, gate.stmts.S)
    )
    assert [type(stmt) for stmt in relevant_stmts] == [
        gate.stmts.S,
        gate.stmts.SqrtX,
    ]

    assert relevant_stmts[0].adjoint
    assert not relevant_stmts[1].adjoint


def test_sqrt_x():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 3, 1)
        sq.u3(
            theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.25 * math.tau, qubit=q[0]
        )

    SquinToCliffordTestPass(test.dialects)(test)
    relevant_stmts = filter_statements_by_type(
        test, (gate.stmts.S, gate.stmts.SqrtY, gate.stmts.SqrtX)
    )

    assert [type(stmt) for stmt in relevant_stmts] == [
        gate.stmts.SqrtX,
    ]
    assert not relevant_stmts[0].adjoint


def test_s_sqrt_x():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 3, 2)
        sq.u3(
            theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.5 * math.tau, qubit=q[0]
        )

    SquinToCliffordTestPass(test.dialects)(test)

    relevant_stmts = filter_statements_by_type(
        test, (gate.stmts.Z, gate.stmts.SqrtY, gate.stmts.S, gate.stmts.SqrtX)
    )
    assert [type(stmt) for stmt in relevant_stmts] == [
        gate.stmts.S,
        gate.stmts.SqrtX,
    ]
    assert not relevant_stmts[0].adjoint
    assert not relevant_stmts[1].adjoint


def test_z_sqrt_x():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 3, 3)
        sq.u3(
            theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.75 * math.tau, qubit=q[0]
        )

    SquinToCliffordTestPass(test.dialects)(test)

    relevant_stmts = filter_statements_by_type(
        test, (gate.stmts.S, gate.stmts.SqrtY, gate.stmts.Z, gate.stmts.SqrtX)
    )

    assert [type(stmt) for stmt in relevant_stmts] == [
        gate.stmts.Z,
        gate.stmts.SqrtX,
    ]
    assert not relevant_stmts[1].adjoint


def test_y():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (2, 0, 0)
        sq.u3(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.Y)


def test_s_y():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (2, 0, 1)
        sq.u3(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.25 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 6), gate.stmts.Y)

    [s_stmt] = filter_statements_by_type(test, (gate.stmts.S,))

    assert not s_stmt.adjoint


def test_x():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (2, 0, 2)
        sq.u3(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.5 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), gate.stmts.X)


def test_sdg_y():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (2, 0, 3)
        sq.u3(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.75 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)

    relevant_stmts = filter_statements_by_type(test, (gate.stmts.S, gate.stmts.Y))
    # Should be Sdag, Y for the op
    assert [type(stmt) for stmt in relevant_stmts] == [
        gate.stmts.S,
        gate.stmts.Y,
    ]
    # The S should be adjoint
    assert relevant_stmts[0].adjoint
