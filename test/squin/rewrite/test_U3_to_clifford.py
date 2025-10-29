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

        return (
            Walk(Chain(Walk(SquinU3ToClifford()), Walk(DeadCodeElimination())))
            .rewrite(mt.code)
            .join(rewrite_result)
        )


def filter_statements_by_type(
    method: ir.Method, types: tuple[type, ...]
) -> list[ir.Statement]:
    return [
        stmt
        for stmt in method.callable_region.blocks[0].stmts
        if isinstance(stmt, types)
    ]


def get_1q_gate_stmts(method: ir.Method) -> list[ir.Statement]:
    return filter_statements_by_type(method, (gate.stmts.SingleQubitGate,))


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
    expected_stmts = [gate.stmts.S] * 3
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    # Should be normal S gates, not adjoint/dagger
    for stmt in actual_stmts:
        assert not stmt.adjoint


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
    expected_stmts = [gate.stmts.Z] * 4
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts


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
    expected_stmts = [gate.stmts.S] * 5
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    for stmt in actual_stmts:
        assert stmt.adjoint


# Checks that Sdag is the first gate that gets generated,
# There is a Y that gets appended afterwards but is not checked
def test_sdag_weirder_case():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        sq.u3(theta=0.5 * math.tau, phi=0.05 * math.tau, lam=0.8 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    expected_stmts = [gate.stmts.S, gate.stmts.Y]
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    assert actual_stmts[0].adjoint


def test_sqrt_y():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # equivalent to sqrt(y) gate
        sq.u3(theta=0.25 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau, qubit=q[0])
        sq.u3(theta=1.25 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    expected_stmts = [gate.stmts.SqrtY] * 2
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts


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
    expected_stmts = [gate.stmts.S, gate.stmts.SqrtY] * 2
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts

    for stmt in actual_stmts:
        assert not stmt.adjoint


def test_h():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 0, 1)
        sq.u3(theta=0.25 * math.tau, phi=0.0 * math.tau, lam=0.5 * math.tau, qubit=q[0])
        sq.u3(theta=1.25 * math.tau, phi=0.0 * math.tau, lam=1.5 * math.tau, qubit=q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    expected_stmts = [gate.stmts.H] * 2
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts


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
    expected_stmts = [gate.stmts.S, gate.stmts.SqrtY] * 2
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts

    for stmt in actual_stmts:
        if type(stmt) is gate.stmts.S:
            assert stmt.adjoint

        if type(stmt) is gate.stmts.SqrtY:
            assert not stmt.adjoint


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
    expected_stmts = [gate.stmts.S, gate.stmts.SqrtX, gate.stmts.S, gate.stmts.SqrtX]
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    for stmt in actual_stmts:
        if type(stmt) is gate.stmts.S:
            assert not stmt.adjoint

        if type(stmt) is gate.stmts.SqrtX:
            assert stmt.adjoint


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
    expected_stmts = [gate.stmts.Z, gate.stmts.SqrtX] * 2
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts

    for stmt in actual_stmts:
        if type(stmt) is gate.stmts.SqrtX:
            assert stmt.adjoint


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
    expected_stmts = [gate.stmts.S, gate.stmts.SqrtX] * 2
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    for stmt in actual_stmts:
        assert stmt.adjoint


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
    expected_stmts = [gate.stmts.SqrtX] * 2
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    for stmt in actual_stmts:
        assert stmt.adjoint


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
    expected_stmts = [gate.stmts.Z, gate.stmts.SqrtY] * 2
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts

    for stmt in actual_stmts:
        if type(stmt) is gate.stmts.SqrtY:
            assert stmt.adjoint


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

    expected_stmts = [gate.stmts.S, gate.stmts.SqrtY] * 2
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts

    for stmt in actual_stmts:
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
    expected_stmts = [gate.stmts.SqrtY] * 2
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    for stmt in actual_stmts:
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
    expected_stmts = [gate.stmts.S, gate.stmts.SqrtY] * 2
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    for stmt in actual_stmts:
        if type(stmt) is gate.stmts.S:
            assert not stmt.adjoint
        if type(stmt) is gate.stmts.SqrtY:
            assert stmt.adjoint


def test_s_dag_sqrt_x():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 3, 0)
        sq.u3(
            theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.0 * math.tau, qubit=q[0]
        )

    SquinToCliffordTestPass(test.dialects)(test)
    expected_stmts = [gate.stmts.S, gate.stmts.SqrtX]
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    for stmt in actual_stmts:
        if type(stmt) is gate.stmts.S:
            assert stmt.adjoint
        if type(stmt) is gate.stmts.SqrtX:
            assert not stmt.adjoint


def test_sqrt_x():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 3, 1)
        sq.u3(
            theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.25 * math.tau, qubit=q[0]
        )

    SquinToCliffordTestPass(test.dialects)(test)
    expected_stmts = [gate.stmts.SqrtX]
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    for stmt in actual_stmts:
        if type(stmt) is gate.stmts.SqrtX:
            assert not stmt.adjoint


def test_s_sqrt_x():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 3, 2)
        sq.u3(
            theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.5 * math.tau, qubit=q[0]
        )

    SquinToCliffordTestPass(test.dialects)(test)
    expected_stmts = [gate.stmts.S, gate.stmts.SqrtX]
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    for stmt in actual_stmts:
        if type(stmt) is gate.stmts.SqrtX:
            assert not stmt.adjoint


def test_z_sqrt_x():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (1, 3, 3)
        sq.u3(
            theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.75 * math.tau, qubit=q[0]
        )

    SquinToCliffordTestPass(test.dialects)(test)
    expected_stmts = [gate.stmts.Z, gate.stmts.SqrtX]
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts
    for stmt in actual_stmts:
        if type(stmt) is gate.stmts.SqrtX:
            assert not stmt.adjoint


def test_y():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (2, 0, 0)
        sq.u3(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    expected_stmts = [gate.stmts.Y]
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts


def test_s_y():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (2, 0, 1)
        sq.u3(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.25 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    expected_stmts = [gate.stmts.S, gate.stmts.Y]
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts

    for stmt in actual_stmts:
        if type(stmt) is gate.stmts.S:
            assert not stmt.adjoint


def test_x():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (2, 0, 2)
        sq.u3(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.5 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    expected_stmts = [gate.stmts.X]
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts


def test_sdg_y():

    @sq.kernel
    def test():
        q = sq.qalloc(4)
        # (2, 0, 3)
        sq.u3(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.75 * math.tau, qubit=q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    expected_stmts = [gate.stmts.S, gate.stmts.Y]
    actual_stmts = get_1q_gate_stmts(test)
    assert [type(stmt) for stmt in actual_stmts] == expected_stmts

    # The S should be adjoint
    assert actual_stmts[0].adjoint
