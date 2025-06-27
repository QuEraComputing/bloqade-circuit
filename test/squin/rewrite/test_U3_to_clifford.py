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


def get_stmt_at_idx(method: ir.Method, idx: int) -> ir.Statement:
    return method.callable_region.blocks[0].stmts.at(idx)


def test_identity():

    @kernel
    def test():

        q = qubit.new(4)
        oper = op.u(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)

    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.Identity)


def test_s():

    @kernel
    def test():
        q = qubit.new(4)
        oper = op.u(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=0.25 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)

    # exercise equivalent_u3_para check
    ## assumes it's already in units of half pi and normalized to [0, 1)
    @kernel
    def test_equiv():
        q = qubit.new(4)
        oper = op.u(theta=math.tau, phi=0.5 * math.tau, lam=0.75 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test_equiv.dialects)(test_equiv)

    assert isinstance(get_stmt_at_idx(test_equiv, 5), op.stmts.S)


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

    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 10), op.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 15), op.stmts.Z)


def test_sdag():

    @kernel
    def test():
        q = qubit.new(4)
        oper = op.u(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=-0.25 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 6), op.stmts.Adjoint)

    @kernel
    def test_equiv():
        q = qubit.new(4)
        oper = op.u(theta=0.0 * math.tau, phi=0.5 * math.tau, lam=0.25 * math.tau)
        qubit.apply(oper, q[0])

    SquinToCliffordTestPass(test_equiv.dialects)(test_equiv)
    assert isinstance(get_stmt_at_idx(test_equiv, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test_equiv, 6), op.stmts.Adjoint)


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

    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 10), op.stmts.SqrtY)


def test_s_sqrt_y():

    @kernel
    def test():

        q = qubit.new(4)
        op0 = op.u(theta=0.25 * math.tau, phi=0.0 * math.tau, lam=0.25 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.0 * math.tau, lam=1.25 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 7), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 12), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 14), op.stmts.SqrtY)


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
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.H)
    assert isinstance(get_stmt_at_idx(test, 10), op.stmts.H)


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
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 6), op.stmts.Adjoint)
    assert isinstance(get_stmt_at_idx(test, 8), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 13), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 14), op.stmts.Adjoint)
    assert isinstance(get_stmt_at_idx(test, 16), op.stmts.SqrtY)


def test_sqrt_y_s():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 1, 0)
        op0 = op.u(theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.0 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=-1.75 * math.tau, lam=0.0 * math.tau)
        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.SqrtY)


def test_s_sqrt_y_s():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 1, 1)
        op0 = op.u(theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.25 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.25 * math.tau, lam=1.25 * math.tau)
        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)

    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 7), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 9), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 14), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 16), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 18), op.stmts.S)


def test_z_sqrt_y_s():

    @kernel
    def test():
        q = qubit.new(1)
        # (1, 1, 2)
        op0 = op.u(theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.5 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.25 * math.tau, lam=1.5 * math.tau)
        qubit.apply(op0, q[0])
        qubit.apply(op1, q[0])

    SquinToCliffordTestPass(test.dialects)(test)

    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 7), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 9), op.stmts.S)

    assert isinstance(get_stmt_at_idx(test, 14), op.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 16), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 18), op.stmts.S)


def test_sdg_sqrt_y_s():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 1, 3)
        op0 = op.u(theta=0.25 * math.tau, phi=0.25 * math.tau, lam=0.75 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.25 * math.tau, lam=1.75 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 6), op.stmts.Adjoint)
    assert isinstance(get_stmt_at_idx(test, 8), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 10), op.stmts.S)

    assert isinstance(get_stmt_at_idx(test, 15), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 16), op.stmts.Adjoint)
    assert isinstance(get_stmt_at_idx(test, 18), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 20), op.stmts.S)


def test_sqrt_y_z():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 2, 0)
        op0 = op.u(theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.0 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=-1.5 * math.tau, lam=0.0 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)

    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 7), op.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 12), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 14), op.stmts.Z)


def test_s_sqrt_y_z():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 2, 1)
        op0 = op.u(theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.25 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.5 * math.tau, lam=-1.75 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)

    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 7), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 9), op.stmts.Z)

    assert isinstance(get_stmt_at_idx(test, 14), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 16), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 18), op.stmts.Z)


def test_z_sqrt_y_z():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 2, 2)
        op0 = op.u(theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.5 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=-0.5 * math.tau, lam=-1.5 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)

    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 7), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 9), op.stmts.Z)

    assert isinstance(get_stmt_at_idx(test, 14), op.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 16), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 18), op.stmts.Z)


def test_sdg_sqrt_y_z():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 2, 3)
        op0 = op.u(theta=0.25 * math.tau, phi=0.5 * math.tau, lam=0.75 * math.tau)
        op1 = op.u(theta=1.25 * math.tau, phi=1.5 * math.tau, lam=-1.25 * math.tau)

        qubit.apply(op0, q[0])
        qubit.apply(op1, q[1])

    SquinToCliffordTestPass(test.dialects)(test)

    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 6), op.stmts.Adjoint)
    assert isinstance(get_stmt_at_idx(test, 8), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 10), op.stmts.Z)

    assert isinstance(get_stmt_at_idx(test, 15), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 16), op.stmts.Adjoint)
    assert isinstance(get_stmt_at_idx(test, 18), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 20), op.stmts.Z)


def test_sqrt_y_sdg():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 3, 0)
        op0 = op.u(theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.0 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 7), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 8), op.stmts.Adjoint)


def test_s_sqrt_y_sdg():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 3, 1)
        op0 = op.u(theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.25 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 7), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 9), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 10), op.stmts.Adjoint)


def test_z_sqrt_y_sdg():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 3, 2)
        op0 = op.u(theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.5 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 7), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 9), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 10), op.stmts.Adjoint)


def test_sdg_sqrt_y_sdg():

    @kernel
    def test():
        q = qubit.new(4)
        # (1, 3, 3)
        op0 = op.u(theta=0.25 * math.tau, phi=0.75 * math.tau, lam=0.75 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 6), op.stmts.Adjoint)
    assert isinstance(get_stmt_at_idx(test, 8), op.stmts.SqrtY)
    assert isinstance(get_stmt_at_idx(test, 10), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 11), op.stmts.Adjoint)


def test_y():

    @kernel
    def test():
        q = qubit.new(4)
        # (2, 0, 0)
        op0 = op.u(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.0 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.Y)


def test_s_y():

    @kernel
    def test():
        q = qubit.new(4)
        # (2, 0, 1)
        op0 = op.u(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.25 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 7), op.stmts.Y)


def test_z_y():

    @kernel
    def test():
        q = qubit.new(4)
        # (2, 0, 2)
        op0 = op.u(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.5 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.Z)
    assert isinstance(get_stmt_at_idx(test, 7), op.stmts.Y)


def test_sdg_y():

    @kernel
    def test():
        q = qubit.new(4)
        # (2, 0, 3)
        op0 = op.u(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.75 * math.tau)
        qubit.apply(op0, q[0])

    SquinToCliffordTestPass(test.dialects)(test)
    assert isinstance(get_stmt_at_idx(test, 5), op.stmts.S)
    assert isinstance(get_stmt_at_idx(test, 6), op.stmts.Adjoint)
    assert isinstance(get_stmt_at_idx(test, 8), op.stmts.Y)
