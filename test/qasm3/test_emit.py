"""Tests for the QASM3 string emitter."""

import textwrap

from bloqade import qasm3
from bloqade.qasm3.emit import QASM3Emitter


def _round_trip(source: str) -> str:
    """Parse QASM3 source, emit back to string."""
    mt = qasm3.loads(source)
    return QASM3Emitter().emit(mt)


def _round_trip_stable(source: str):
    """Verify emit -> parse -> emit produces identical output."""
    mt1 = qasm3.loads(source)
    emitter = QASM3Emitter()
    emitted1 = emitter.emit(mt1)
    mt2 = qasm3.loads(emitted1)
    mt2.verify()
    emitted2 = QASM3Emitter().emit(mt2)
    assert emitted1 == emitted2


BELL_STATE = textwrap.dedent("""\
    OPENQASM 3.0;
    qubit[2] q;
    bit[2] c;
    h q[0];
    cx q[0], q[1];
    c[0] = measure q[0];
    c[1] = measure q[1];
""")


def test_bell_state_emit():
    result = _round_trip(BELL_STATE)
    assert "OPENQASM 3.0;" in result
    assert "qubit[2]" in result
    assert "bit[2]" in result
    assert "h q[0];" in result
    assert "cx q[0], q[1];" in result
    assert "measure q[0];" in result


def test_bell_state_round_trip_stable():
    _round_trip_stable(BELL_STATE)


ALL_GATES = textwrap.dedent("""\
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[3] q;
    bit[3] c;
    h q[0];
    x q[1];
    y q[2];
    z q[0];
    s q[1];
    t q[2];
    rx(pi) q[0];
    ry(1.5) q[1];
    rz(0.25) q[2];
    cx q[0], q[1];
    cy q[1], q[2];
    cz q[0], q[2];
    U(pi, 1.5, 0.25) q[0];
    reset q[1];
    c[0] = measure q[0];
    c[1] = measure q[1];
    c[2] = measure q[2];
""")


def test_all_gates_round_trip_stable():
    _round_trip_stable(ALL_GATES)


def test_all_gates_emit_contains_expected():
    result = _round_trip(ALL_GATES)
    for gate in ["h ", "x ", "y ", "z ", "s ", "t "]:
        assert gate in result
    assert "rx(" in result
    assert "ry(" in result
    assert "rz(" in result
    assert "cx " in result
    assert "cy " in result
    assert "cz " in result
    assert "U(" in result
    assert "reset " in result
    assert "measure " in result


def test_emit_produces_valid_qasm3_header():
    result = _round_trip(BELL_STATE)
    lines = result.strip().split("\n")
    assert lines[0] == "OPENQASM 3.0;"
    assert lines[1] == 'include "stdgates.inc";'
