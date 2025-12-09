from kirin import ir, rewrite
from kirin.dialects import py

from bloqade.test_utils import assert_nodes
from bloqade.squin.gate.stmts import U3
from bloqade.gemini.rewrite.initialize import __RewriteU3ToInitialize
from bloqade.gemini.dialects.logical.stmts import Initialize


def test_rewrite_u3_to_initialize():
    theta = ir.TestValue()
    phi = ir.TestValue()
    qubits = ir.TestValue()
    test_block = ir.Block(
        [
            lam_stmt := py.Constant(1.0),
            U3(theta, phi, lam_stmt.result, qubits),
        ]
    )

    expected_block = ir.Block(
        [
            lam_stmt := py.Constant(1.0),
            Initialize(theta, phi, lam_stmt.result, qubits),
        ]
    )

    rewrite.Walk(__RewriteU3ToInitialize()).rewrite(test_block)

    assert_nodes(test_block, expected_block)
