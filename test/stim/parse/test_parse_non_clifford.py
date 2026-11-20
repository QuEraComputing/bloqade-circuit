import math

import pytest

from bloqade import stim, squin
from bloqade.stim.parse import loads

from .base import codegen


@pytest.mark.parametrize("strict", [False, True])
def test_squin_non_clifford_round_trip(strict):
    @squin.kernel
    def circuit():
        q = squin.qalloc(6)
        squin.t(q[0])
        squin.t_adj(q[1])
        squin.rx(0.3 * math.pi, q[2])
        squin.ry(-0.25 * math.pi, q[3])
        squin.rz(0.125 * math.pi, q[4])
        squin.u3(0.3 * math.pi, 0.24 * math.pi, 0.49 * math.pi, q[5])

    original = str(stim.Circuit(circuit)).strip()
    assert original == (
        "S[T] 0\n"
        "S_DAG[T] 1\n"
        "I[R_X(theta=0.3*pi)] 2\n"
        "I[R_Y(theta=-0.25*pi)] 3\n"
        "I[R_Z(theta=0.125*pi)] 4\n"
        "I[U3(theta=0.3*pi, phi=0.24*pi, lambda=0.49*pi)] 5"
    )
    assert codegen(loads(original, error_unknown_nonstim=strict)) == original


@pytest.mark.parametrize(
    "tagged, expected",
    [
        ("S[T] 1 0", "S[T] 1 0"),
        ("I[R_X(theta=0.3*pi)] 1 0", "I[R_X(theta=0.3*pi)] 1 0"),
        ("S[annotation] 0", "S 0"),
        ("S_DAG[annotation] 0", "S_DAG 0"),
        ("I[annotation] 0", "I 0"),
        ("I[R_Z(theta=2e-08*pi)] 0", "I[R_Z(theta=2e-08*pi)] 0"),
        ("I[R_X(theta=unknown*pi)] 0", "I 0"),
        ("X[T] 0", "X 0"),
    ],
)
def test_gate_annotations(tagged, expected):
    assert codegen(loads(tagged, error_unknown_nonstim=True)) == expected
