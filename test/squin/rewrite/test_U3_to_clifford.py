import math

from kirin import ir
from kirin.rewrite import Walk, Chain
from kirin.passes.abc import Pass
from kirin.rewrite.dce import DeadCodeElimination

from bloqade.squin import op, qubit, kernel
from bloqade.squin.rewrite.U3_to_clifford import SquinU3ToClifford


class SquinToCliffordTestPass(Pass):

    def unsafe_run(self, mt: ir.Method):
        return Walk(
            Chain(Walk(SquinU3ToClifford()), Walk(DeadCodeElimination()))
        ).rewrite(mt.code)


def filter_statements_by_type(method: ir.Method, types: tuple[type, ...]) -> list[type]:
    return [
        type(stmt)
        for stmt in method.callable_region.blocks[0].stmts
        if isinstance(stmt, types)
    ]


def test_identity():

    @kernel
    def test():

        q = qubit.new(4)
        oper = op.u(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.Identity]
    assert filtered_stmts == expected_stmts


def test_s():

    @kernel
    def test():
        q = qubit.new(4)
        oper = op.u(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=0.25 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S]
    assert filtered_stmts == expected_stmts

    # exercise equivalent_u3_para check
    ## assumes it's already in units of half pi and normalized to [0, 1)
    @kernel
    def test_equiv():
        q = qubit.new(4)
        oper = op.u(theta=math.tau, phi=0.5 * math.tau, lam=0.75 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test_equiv.dialects)(test_equiv)
    filtered_stmts = filter_statements_by_type(test_equiv, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S]
    assert filtered_stmts == expected_stmts


def test_s_alternative():

    @kernel
    def test():
        q = qubit.new(4)
        oper = op.u(theta=0.0, phi=0.25 * math.tau, lam=0.0)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S]
    assert filtered_stmts == expected_stmts


def test_z():

    @kernel
    def test():
        q = qubit.new(4)
        # nice positive representation
        op0 = op.u(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=0.5 * math.tau)
        # wrap around
        op1 = op.u(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=1.5 * math.tau)
        # go backwards
        op2 = op.u(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=-0.5 * math.tau)
        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])
        qubit.apply(op2, q[2])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.Z] * 3
    assert filtered_stmts == expected_stmts


def test_z_alternative():

    @kernel
    def test():
        q = qubit.new(4)
        oper = op.u(theta=0.0, phi=0.5 * math.tau, lam=0.0)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.Z]
    assert filtered_stmts == expected_stmts


def test_sdag():

    @kernel
    def test():
        q = qubit.new(4)
        oper = op.u(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=-0.25 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.Adjoint]
    assert filtered_stmts == expected_stmts

    @kernel
    def test_equiv():
        q = qubit.new(4)
        oper = op.u(theta=0.0 * math.tau, phi=0.5 * math.tau, lam=0.25 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test_equiv.dialects)(test_equiv)
    filtered_stmts = filter_statements_by_type(test_equiv, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.Adjoint]
    assert filtered_stmts == expected_stmts


def test_sdag_alternative_negative():

    @kernel
    def test():
        q = qubit.new(4)
        oper = op.u(theta=0.0, phi=-0.25 * math.tau, lam=0.0)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.Adjoint]
    assert filtered_stmts == expected_stmts


def test_sdag_alternative():

    @kernel
    def test():
        q = qubit.new(4)
        oper = op.u(theta=0.0, phi=0.75 * math.tau, lam=0.0)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.Adjoint]
    assert filtered_stmts == expected_stmts


def test_sdag_weird_case():

    @kernel
    def test():
        q = qubit.new(4)
        oper = op.u(theta=2 * math.tau, phi=0.7 * math.tau, lam=0.05 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.Adjoint]
    assert filtered_stmts == expected_stmts


def test_sdag_weirder_case():

    @kernel
    def test():
        q = qubit.new(4)
        oper = op.u(theta=0.5 * math.tau, phi=0.05 * math.tau, lam=0.8 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.Adjoint]
    # Technically a Y afterwards, just want to check the first two
    # stmts are S + Adjoint
    assert filtered_stmts[:-1] == expected_stmts


def test_sqrt_y():

    @kernel
    def test():
        q = qubit.new(4)
        op0 = op.u(theta=0.25 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau)
        # equivalent to sqrt(y) gate
        op1 = op.u(theta=1.25 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.SqrtY] * 2
    assert filtered_stmts == expected_stmts


def test_s_sqrt_y():

    @kernel
    def test():

        q = qubit.new(4)
        op0 = op.u(theta=0.25 * math.tau, phi=0.0 * math.tau, lam=0.25 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.0 * math.tau, lam=1.25 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.SqrtY, op.stmts.S, op.stmts.SqrtY]
    assert filtered_stmts == expected_stmts


def test_h():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 0, 1)
        op0 = op.u(theta=0.25 * math.tau, phi=0.0 * math.tau, lam=0.5 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=0.0 * math.tau, lam=1.5 * math.tau)
        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.H] * 2
    assert filtered_stmts == expected_stmts


def test_sdg_sqrt_y():

    @kernel()
    def test():
        q = qubit.new(4)
        # (1, 0, 3)
        op0 = op.u(theta=0.25 * math.tau, phi=0.0 * math.tau, lam=0.75 * math.tau)
        op1 = op.u(theta=-1.75 * math.tau, phi=0.0 * math.tau, lam=-1.25 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.Adjoint, op.stmts.SqrtY] * 2
    assert filtered_stmts == expected_stmts


def test_s_sqrt_x_dag():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 1, 0)
        op0 = op.u(theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.0 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=-1.75 * math.tau, lam=0.0 * math.tau)
        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.SqrtX, op.stmts.Adjoint] * 2
    assert filtered_stmts == expected_stmts


def test_z_sqrt_x_dag():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 1, 1)
        op0 = op.u(theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.25 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.25 * math.tau, lam=1.25 * math.tau)
        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)

    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.Z, op.stmts.SqrtX, op.stmts.Adjoint] * 2
    assert filtered_stmts == expected_stmts


def test_s_dag_sqrt_x_dag():

    @kernel
    def test():
        q = qubit.new(1)
        # (1, 1, 2)
        op0 = op.u(theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.5 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.25 * math.tau, lam=1.5 * math.tau)
        qubit.apply(op0, q[0])
        qubit.apply(op1, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [
        op.stmts.S,
        op.stmts.Adjoint,
        op.stmts.SqrtX,
        op.stmts.Adjoint,
    ] * 2
    assert filtered_stmts == expected_stmts


def test_sqrt_x_dag():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 1, 3)
        op0 = op.u(theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.75 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.25 * math.tau, lam=1.75 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.SqrtX, op.stmts.Adjoint] * 2
    assert filtered_stmts == expected_stmts


def test_z_sqrt_y_dag():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 2, 0)
        op0 = op.u(theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.0 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=-1.5 * math.tau, lam=0.0 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.Z, op.stmts.SqrtY, op.stmts.Adjoint] * 2
    assert filtered_stmts == expected_stmts


def test_s_dag_sqrt_y_dag():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 2, 1)
        op0 = op.u(theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.25 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.5 * math.tau, lam=-1.75 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [
        op.stmts.S,
        op.stmts.Adjoint,
        op.stmts.SqrtY,
        op.stmts.Adjoint,
    ] * 2
    assert filtered_stmts == expected_stmts


def test_sqrt_y_dag():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 2, 2)
        op0 = op.u(theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.5 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=-0.5 * math.tau, lam=-1.5 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)

    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.SqrtY, op.stmts.Adjoint] * 2
    assert filtered_stmts == expected_stmts


def test_s_sqrt_y_dag():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 2, 3)
        op0 = op.u(theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.75 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.5 * math.tau, lam=-1.25 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.SqrtY, op.stmts.Adjoint] * 2
    assert filtered_stmts == expected_stmts


def test_s_dag_sqrt_x():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 3, 0)
        u3 = op.u(theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.0 * math.tau)
        qubit.apply(u3, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.Adjoint, op.stmts.SqrtX]
    assert filtered_stmts == expected_stmts


def test_sqrt_x():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 3, 1)
        u3 = op.u(theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.25 * math.tau)
        qubit.apply(u3, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.SqrtX]
    assert filtered_stmts == expected_stmts


def test_s_sqrt_x():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 3, 2)
        u3 = op.u(theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.5 * math.tau)
        qubit.apply(u3, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.SqrtX]
    assert filtered_stmts == expected_stmts


def test_z_sqrt_x():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 3, 3)
        op0 = op.u(theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.75 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.Z, op.stmts.SqrtX]
    assert filtered_stmts == expected_stmts


def test_y():

    @kernel
    def test():
        q = qubit.new(4)
        # (2, 0, 0)
        op0 = op.u(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.Y]
    assert filtered_stmts == expected_stmts


def test_s_y():

    @kernel
    def test():
        q = qubit.new(4)
        # (2, 0, 1)
        op0 = op.u(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.25 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.Y]
    assert filtered_stmts == expected_stmts


def test_x():

    @kernel
    def test():
        q = qubit.new(4)
        # (2, 0, 2)
        op0 = op.u(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.5 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.X]
    assert filtered_stmts == expected_stmts


def test_sdg_y():

    @kernel
    def test():
        q = qubit.new(4)
        # (2, 0, 3)
        op0 = op.u(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.75 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    filtered_stmts = filter_statements_by_type(test, (op.stmts.Operator,))
    expected_stmts = [op.stmts.S, op.stmts.Adjoint, op.stmts.Y]
    assert filtered_stmts == expected_stmts
