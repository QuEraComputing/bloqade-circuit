import math

import numpy as np
from kirin import ir, rewrite
from kirin.dialects import py

from bloqade.squin.gate import stmts as gate_stmts
from bloqade.test_utils import assert_nodes
from bloqade.squin.rewrite.merge_U3 import RewriteMergeU3


def _u3_matrix(theta: float, phi: float, lam: float) -> np.ndarray:
    theta *= 2 * np.pi
    phi *= 2 * np.pi
    lam *= 2 * np.pi
    return np.array(
        [
            [
                np.cos(theta / 2),
                -np.exp(1j * lam) * np.sin(theta / 2),
            ],
            [
                np.exp(1j * phi) * np.sin(theta / 2),
                np.exp(1j * (phi + lam)) * np.cos(theta / 2),
            ],
        ]
    )


def _normalize_u2(u: np.ndarray) -> np.ndarray:
    # Normalize to U(2) by removing global phase.
    gamma = 0.5 * np.angle(np.linalg.det(u))
    return u * np.exp(-1j * gamma)


def _unwrap_py_constant_float(v: ir.SSAValue) -> float:
    assert isinstance(v.owner, py.Constant)
    return float(v.owner.value.unwrap())


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


def test_rewrite_different_qubits_no_merge():
    # consecutive U3s on different qubits should not be merged
    qubits1 = ir.TestValue()
    qubits2 = ir.TestValue()
    theta1 = py.Constant(0.5)
    phi1 = py.Constant(0.1)
    lam1 = py.Constant(0.2)
    theta2 = py.Constant(0.3)
    phi2 = py.Constant(0.4)
    lam2 = py.Constant(0.5)

    test_block = ir.Block(
        [
            gate_stmts.U3(
                qubits=qubits1,
                theta=theta1.result,
                phi=phi1.result,
                lam=lam1.result,
            ),
            gate_stmts.U3(
                qubits=qubits2,
                theta=theta2.result,
                phi=phi2.result,
                lam=lam2.result,
            ),
        ]
    )

    expected_block = ir.Block(
        [
            gate_stmts.U3(
                qubits=qubits1,
                theta=theta1.result,
                phi=phi1.result,
                lam=lam1.result,
            ),
            gate_stmts.U3(
                qubits=qubits2,
                theta=theta2.result,
                phi=phi2.result,
                lam=lam2.result,
            ),
        ]
    )

    rule = rewrite.Walk(RewriteMergeU3())
    rule.rewrite(test_block)

    assert_nodes(test_block, expected_block)


def test_rewrite_nonconstant_param_no_merge():
    # if any parameter is not a literal constant, the rule should skip merging
    test_qubits = ir.TestValue()
    nonconst_theta = ir.TestValue()
    phi1 = py.Constant(0.1)
    lam1 = py.Constant(0.2)
    theta2 = py.Constant(0.3)
    phi2 = py.Constant(0.4)
    lam2 = py.Constant(0.5)

    test_block = ir.Block(
        [
            gate_stmts.U3(
                qubits=test_qubits,
                theta=nonconst_theta,
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

    expected_block = ir.Block(
        [
            gate_stmts.U3(
                qubits=test_qubits,
                theta=nonconst_theta,
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

    rule = rewrite.Walk(RewriteMergeU3())
    rule.rewrite(test_block)

    assert_nodes(test_block, expected_block)


def test_rewrite_three_u3_merges_to_one_equivalent_matrix():
    test_qubits = ir.TestValue()
    # random-ish parameters in turns (same convention as RewriteMergeU3)
    # Keep theta away from 0 to avoid ambiguous decompositions.

    theta1, phi1, lam1 = 0.3, 0.1, -0.2
    theta2, phi2, lam2 = -0.7, 0.9, 0.4
    theta3, phi3, lam3 = math.pi / 3, -math.pi / 5, math.pi / 7

    c_t1, c_p1, c_l1 = py.Constant(theta1), py.Constant(phi1), py.Constant(lam1)
    c_t2, c_p2, c_l2 = py.Constant(theta2), py.Constant(phi2), py.Constant(lam2)
    c_t3, c_p3, c_l3 = py.Constant(theta3), py.Constant(phi3), py.Constant(lam3)

    test_block = ir.Block(
        [
            gate_stmts.U3(
                qubits=test_qubits,
                theta=c_t1.result,
                phi=c_p1.result,
                lam=c_l1.result,
            ),
            gate_stmts.U3(
                qubits=test_qubits,
                theta=c_t2.result,
                phi=c_p2.result,
                lam=c_l2.result,
            ),
            gate_stmts.U3(
                qubits=test_qubits,
                theta=c_t3.result,
                phi=c_p3.result,
                lam=c_l3.result,
            ),
        ]
    )
    expected_theta = py.Constant(0.8657155563999239)
    expected_phi = py.Constant(-1.144168331300085)
    expected_lam = py.Constant(1.901389486255007)
    expected_block = ir.Block(
        [
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
    rule.rewrite(test_block)

    assert_nodes(test_block, expected_block)
