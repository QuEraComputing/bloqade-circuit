from kirin.dialects import scf

from bloqade import qasm2
from bloqade.qasm2.passes.parallel import ParallelToGlobal


def test_basic_rewrite():

    @qasm2.extended
    def main():
        q = qasm2.qreg(2)

        qasm2.parallel.u(theta=0.3, phi=0.1, lam=0.2, qargs=q)

    result = ParallelToGlobal(qasm2.extended)(main)
    assert result.has_done_something

    main.print()

    region = main.code.regions[0]
    assert 1 == sum(
        map(lambda s: isinstance(s, qasm2.dialects.glob.UGate), region.stmts())
    )
    assert not any(
        map(lambda s: isinstance(s, qasm2.dialects.parallel.UGate), region.stmts())
    )


def test_if_rewrite():
    @qasm2.extended
    def main():
        q = qasm2.qreg(4)

        qasm2.parallel.u(theta=0.3, phi=0.1, lam=0.2, qargs=[q[0], q[1]])

        c = qasm2.creg(4)
        qasm2.measure(q, c)

        if c[0] == 1:
            qasm2.parallel.u(theta=0.3, phi=0.1, lam=0.2, qargs=q)

        return q

    result = ParallelToGlobal(qasm2.extended)(main)
    assert result.has_done_something

    main.print()

    region = main.code.regions[0]
    assert 1 == sum(
        map(lambda s: isinstance(s, qasm2.dialects.parallel.UGate), region.stmts())
    )

    assert isinstance(if_stmt := list(region.stmts())[-2], scf.IfElse)
    assert 1 == sum(
        map(
            lambda s: isinstance(s, qasm2.dialects.glob.UGate),
            if_stmt.then_body.stmts(),
        )
    )


def test_should_not_be_rewritten():

    @qasm2.extended
    def main():
        q = qasm2.qreg(3)

        qasm2.parallel.u(theta=0.3, phi=0.1, lam=0.2, qargs=[q[0], q[2]])

    result = ParallelToGlobal(qasm2.extended)(main)
    assert not result.has_done_something

    region = main.code.regions[0]
    assert 1 == sum(
        map(lambda s: isinstance(s, qasm2.dialects.parallel.UGate), region.stmts())
    )
    assert not any(
        map(lambda s: isinstance(s, qasm2.dialects.glob.UGate), region.stmts())
    )


def test_multiple_registers():
    @qasm2.extended
    def main():
        q1 = qasm2.qreg(3)
        q2 = qasm2.qreg(2)

        qasm2.parallel.u(theta=0.3, phi=0.1, lam=0.2, qargs=[q1[0], q2[1]])

        qasm2.parallel.u(theta=0.3, phi=0.1, lam=0.2, qargs=q1)
        qasm2.parallel.u(theta=0.3, phi=0.1, lam=0.2, qargs=q2)

        q_all = [q1[0], q1[1], q1[2], q2[0], q2[1]]
        qasm2.parallel.u(theta=0.3, phi=0.1, lam=0.2, qargs=q_all)

        q_not_quite_all = [q1[0], q1[1], q1[2], q2[0]]
        qasm2.parallel.u(theta=0.3, phi=0.1, lam=0.2, qargs=q_not_quite_all)

    result = ParallelToGlobal(qasm2.extended)(main)

    assert result.has_done_something

    main.print()

    region = main.code.regions[0]
    assert 3 == sum(
        map(lambda s: isinstance(s, qasm2.dialects.parallel.UGate), region.stmts())
    )
    assert 2 == sum(
        map(lambda s: isinstance(s, qasm2.dialects.glob.UGate), region.stmts())
    )


def test_reverse_order():
    @qasm2.extended
    def main():
        q = qasm2.qreg(2)
        q2 = qasm2.qreg(2)

        qasm2.parallel.u(theta=0.3, phi=0.1, lam=0.2, qargs=[q[1], q[0]])

        qasm2.parallel.u(theta=0.3, phi=0.1, lam=0.2, qargs=[q2[1], q[0]])

    result = ParallelToGlobal(qasm2.extended)(main)

    assert result.has_done_something

    main.print()

    region = main.code.regions[0]
    assert 1 == sum(
        map(lambda s: isinstance(s, qasm2.dialects.parallel.UGate), region.stmts())
    )
    assert 1 == sum(
        map(lambda s: isinstance(s, qasm2.dialects.glob.UGate), region.stmts())
    )
