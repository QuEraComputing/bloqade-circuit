from kirin import ir, rewrite
from kirin.dialects import py

from bloqade.squin.gate import stmts as gate_stmts
from bloqade.test_utils import assert_nodes
from bloqade.squin.rewrite.merge_U3 import RewriteMergeU3


def test_rewrite_theta():
    # keep single U3 as is
    test_qubits = ir.TestValue()
    theta = py.Constant(0.5)
    phi = py.Constant(0.0)
    lam = py.Constant(0.0)
    test_block = ir.Block(
        [
            gate_stmts.U3(
                qubits=test_qubits, theta=theta.result, phi=phi.result, lam=lam.result
            )
        ]
    )

    expected_block = ir.Block(
        [
            gate_stmts.U3(
                qubits=test_qubits, theta=theta.result, phi=phi.result, lam=lam.result
            ),
        ]
    )

    rule = rewrite.Walk(RewriteMergeU3())
    rule.rewrite(test_block)

    assert_nodes(test_block, expected_block)


def test_rewrite_random_two_U3():
    test_qubits = ir.TestValue()
    theta1 = py.Constant(0.5)
    phi1 = py.Constant(0.1)
    lam1 = py.Constant(0.2)
    theta2 = py.Constant(0.3)
    phi2 = py.Constant(0.4)
    lam2 = py.Constant(0.5)
    test_block = ir.Block(
        [
            gate_stmts.U3(
                qubits=test_qubits,
                theta=theta1.result,
                phi=phi1.result,
                lam=lam1.result,
            ),
            gate_stmts.U3(
                qubits=test_qubits,
                theta=theta2.result,
                phi=phi2.result,
                lam=lam2.result,
            ),
        ]
    )

    # Precomputed expected parameters after merging

    expected_block = ir.Block(
        [
            expected_theta := py.Constant(0.2),
            expected_phi := py.Constant(-0.1),
            expected_lam := py.Constant(0.1),
            gate_stmts.U3(
                qubits=test_qubits,
                theta=expected_theta.result,
                phi=expected_phi.result,
                lam=expected_lam.result,
            ),
        ]
    )

    rule = rewrite.Walk(RewriteMergeU3())
    rule.rewrite(test_block)

    assert_nodes(test_block, expected_block)
