from kirin import ir, rewrite
from kirin.dialects import py

from bloqade.squin.gate import stmts as gate_stmts
from bloqade.test_utils import assert_nodes
from bloqade.squin.rewrite.non_clifford_to_U3 import RewriteNonCliffordToU3


def test_rewrite_T():
    test_qubits = ir.TestValue()
    test_block = ir.Block([gate_stmts.T(qubits=test_qubits, adjoint=False)])

    expected_block = ir.Block(
        [
            theta := py.Constant(0.0),
            phi := py.Constant(0.0),
            lam := py.Constant(1.0 / 8.0),
            gate_stmts.U3(
                qubits=test_qubits,
                theta=theta.result,
                phi=phi.result,
                lam=lam.result,
            ),
        ]
    )

    rule = rewrite.Walk(RewriteNonCliffordToU3())
    rule.rewrite(test_block)

    assert_nodes(test_block, expected_block)


def test_rewrite_Tadj():
    test_qubits = ir.TestValue()
    test_block = ir.Block([gate_stmts.T(qubits=test_qubits, adjoint=True)])

    expected_block = ir.Block(
        [
            theta := py.Constant(0.0),
            phi := py.Constant(0.0),
            lam := py.Constant(-1.0 / 8.0),
            gate_stmts.U3(
                qubits=test_qubits,
                theta=theta.result,
                phi=phi.result,
                lam=lam.result,
            ),
        ]
    )

    rule = rewrite.Walk(RewriteNonCliffordToU3())
    rule.rewrite(test_block)

    assert_nodes(test_block, expected_block)


def test_rewrite_Ry():
    test_qubits = ir.TestValue()
    angle = ir.TestValue()
    test_block = ir.Block([gate_stmts.Ry(qubits=test_qubits, angle=angle)])

    expected_block = ir.Block(
        [
            phi := py.Constant(0.0),
            lam := py.Constant(0.0),
            gate_stmts.U3(
                qubits=test_qubits,
                theta=angle,
                phi=phi.result,
                lam=lam.result,
            ),
        ]
    )

    rule = rewrite.Walk(RewriteNonCliffordToU3())
    rule.rewrite(test_block)

    assert_nodes(test_block, expected_block)


def test_rewrite_Rz():
    test_qubits = ir.TestValue()
    angle = ir.TestValue()
    test_block = ir.Block([gate_stmts.Rz(qubits=test_qubits, angle=angle)])

    expected_block = ir.Block(
        [
            theta := py.Constant(0.0),
            phi := py.Constant(0.0),
            gate_stmts.U3(
                qubits=test_qubits,
                theta=theta.result,
                phi=phi.result,
                lam=angle,
            ),
        ]
    )

    rule = rewrite.Walk(RewriteNonCliffordToU3())
    rule.rewrite(test_block)

    assert_nodes(test_block, expected_block)


def test_rewrite_Rx():
    test_qubits = ir.TestValue()
    angle = ir.TestValue()
    test_block = ir.Block([gate_stmts.Rx(qubits=test_qubits, angle=angle)])

    expected_block = ir.Block(
        [
            phi := py.Constant(-0.25),
            lam := py.Constant(0.25),
            gate_stmts.U3(
                qubits=test_qubits,
                theta=angle,
                phi=phi.result,
                lam=lam.result,
            ),
        ]
    )

    rule = rewrite.Walk(RewriteNonCliffordToU3())
    rule.rewrite(test_block)

    assert_nodes(test_block, expected_block)


def test_no_op():
    test_qubits = ir.TestValue()
    angle = ir.TestValue()
    test_block = ir.Block(
        [gate_stmts.U3(qubits=test_qubits, theta=angle, phi=angle, lam=angle)]
    )

    expected_block = ir.Block(
        [gate_stmts.U3(qubits=test_qubits, theta=angle, phi=angle, lam=angle)]
    )

    rule = rewrite.Walk(RewriteNonCliffordToU3())
    rule.rewrite(test_block)

    assert_nodes(test_block, expected_block)
