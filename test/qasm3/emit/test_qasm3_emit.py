"""Tests for the QASM3 emitter: string output, round-trip stability, custom gates."""

import textwrap

import pytest

from bloqade import qasm3
from bloqade.qasm3.emit import QASM3Emitter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit(source: str) -> str:
    """Parse QASM3 source, emit back to string."""
    return QASM3Emitter().emit(qasm3.loads(source))


def _assert_round_trip_stable(source: str):
    """emit(parse(emit(parse(source)))) == emit(parse(source))."""
    emitted1 = _emit(source)
    emitted2 = _emit(emitted1)
    assert emitted1 == emitted2, (
        f"Round trip not stable.\nFirst:\n{emitted1}\nSecond:\n{emitted2}"
    )


# ---------------------------------------------------------------------------
# Basic emit
# ---------------------------------------------------------------------------

BELL_STATE = textwrap.dedent("""\
    OPENQASM 3.0;
    qubit[2] q;
    bit[2] c;
    h q[0];
    cx q[0], q[1];
    c[0] = measure q[0];
    c[1] = measure q[1];
""")


def test_emit_header():
    """Emitted output starts with OPENQASM 3.0 and stdgates include."""
    result = _emit(BELL_STATE)
    lines = result.strip().split("\n")
    assert lines[0] == "OPENQASM 3.0;"
    assert lines[1] == 'include "stdgates.inc";'


def test_emit_bell_state():
    """Bell state emits expected gate and measurement lines."""
    result = _emit(BELL_STATE)
    assert "qubit[2]" in result
    assert "bit[2]" in result
    assert "h q[0];" in result
    assert "cx q[0], q[1];" in result
    assert "measure q[0];" in result


def test_emit_all_gates():
    """Every supported gate appears in emitted output."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[3] q;
        bit[3] c;
        h q[0]; x q[1]; y q[2]; z q[0]; s q[1]; t q[2];
        rx(pi) q[0]; ry(1.5) q[1]; rz(0.25) q[2];
        cx q[0], q[1]; cy q[1], q[2]; cz q[0], q[2];
        U(pi, 1.5, 0.25) q[0];
        reset q[1];
        c[0] = measure q[0]; c[1] = measure q[1]; c[2] = measure q[2];
    """)
    result = _emit(source)
    for tok in ["h ", "x ", "y ", "z ", "s ", "t ", "rx(", "ry(", "rz(",
                "cx ", "cy ", "cz ", "U(", "reset ", "measure "]:
        assert tok in result, f"Missing {tok!r} in emitted output"


# ---------------------------------------------------------------------------
# Round-trip stability (parametrized)
# ---------------------------------------------------------------------------

ROUND_TRIP_PROGRAMS = [
    pytest.param(BELL_STATE, id="bell-state"),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "x q[0];\ny q[1];\nc[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="single-x-y",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\nbit[3] c;\n'
        "z q[0];\ns q[1];\nt q[2];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\nc[2] = measure q[2];\n",
        id="single-z-s-t",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "rx(pi) q[0];\nry(0.5) q[1];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="rotation-rx-ry",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "cx q[0], q[1];\nc[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="two-qubit-cx",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "U(1.5, 0.25, 0.5) q[0];\nc[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="u-gate",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[5] q;\nbit[5] c;\n'
        "h q[0];\nx q[1];\nry(pi) q[2];\ncx q[3], q[4];\nU(0.5, 1.5, 0.25) q[0];\n"
        "t q[1];\ncz q[2], q[3];\nrx(0.1) q[4];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\nc[2] = measure q[2];\n"
        "c[3] = measure q[3];\nc[4] = measure q[4];\n",
        id="mixed-large",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "c[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="measure-only",
    ),
]


@pytest.mark.parametrize("source", ROUND_TRIP_PROGRAMS)
def test_emit_parse_round_trip(source: str):
    """emit(parse(emit(parse(source)))) == emit(parse(source))."""
    _assert_round_trip_stable(source)


# ---------------------------------------------------------------------------
# Custom gate emission (decorator-built programs)
# ---------------------------------------------------------------------------


def test_emit_custom_gate_definition():
    """Emitter produces a gate definition block for a custom gate."""

    @qasm3.gate
    def bell_gate(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.h(a)
        qasm3.cx(a, b)

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        bell_gate(q[0], q[1])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        gate bell_gate a, b {
          h a;
          cx a, b;
        }

        qubit[2] q;
        bell_gate q[0], q[1];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_parameterized_gate():
    """Classical params are separated from qubit args in gate definition."""

    @qasm3.gate
    def my_rot(q: qasm3.Qubit, theta: float):
        qasm3.rx(q, theta)

    @qasm3.main
    def prog():
        q = qasm3.qreg(1)
        my_rot(q[0], 1.57)

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        gate my_rot(theta) q {
          rx(theta) q;
        }

        qubit[1] q;
        my_rot(1.57) q[0];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_multiple_custom_gates():
    """All custom gates used in a program get definitions emitted."""

    @qasm3.gate
    def prep(q: qasm3.Qubit):
        qasm3.h(q)

    @qasm3.gate
    def entangle(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.cx(a, b)

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        prep(q[0])
        entangle(q[0], q[1])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        gate prep q {
          h q;
        }

        gate entangle a, b {
          cx a, b;
        }

        qubit[2] q;
        prep q[0];
        entangle q[0], q[1];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_gate_not_duplicated():
    """A gate called multiple times is only defined once."""

    @qasm3.gate
    def my_x(q: qasm3.Qubit):
        qasm3.x(q)

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        my_x(q[0])
        my_x(q[1])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        gate my_x q {
          x q;
        }

        qubit[2] q;
        my_x q[0];
        my_x q[1];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_full_program_with_measure():
    """Full program: gate def + calls + measurement emits valid QASM3."""

    @qasm3.gate
    def bell(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.h(a)
        qasm3.cx(a, b)

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        c = qasm3.bitreg(2)
        bell(q[0], q[1])
        qasm3.measure(q[0], c[0])
        qasm3.measure(q[1], c[1])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        gate bell a, b {
          h a;
          cx a, b;
        }

        qubit[2] q;
        bit[2] c;
        bell q[0], q[1];
        c[0] = measure q[0];
        c[1] = measure q[1];
    """)
    assert QASM3Emitter().emit(prog) == expected

# ---------------------------------------------------------------------------
# include_files option
# ---------------------------------------------------------------------------

SIMPLE_PROGRAM = textwrap.dedent("""\
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[1] q;
    bit[1] c;
    h q[0];
    c[0] = measure q[0];
""")


def test_include_files_default():
    """Default include_files produces stdgates.inc."""
    result = QASM3Emitter().emit(qasm3.loads(SIMPLE_PROGRAM))
    lines = result.strip().split("\n")
    assert lines[0] == "OPENQASM 3.0;"
    assert lines[1] == 'include "stdgates.inc";'


def test_include_files_empty():
    """Empty include_files produces no include lines."""
    result = QASM3Emitter(include_files=[]).emit(qasm3.loads(SIMPLE_PROGRAM))
    lines = result.strip().split("\n")
    assert lines[0] == "OPENQASM 3.0;"
    assert not lines[1].startswith("include")


def test_include_files_custom():
    """Custom include_files produces the specified include lines."""
    emitter = QASM3Emitter(include_files=["custom_gates.inc"])
    result = emitter.emit(qasm3.loads(SIMPLE_PROGRAM))
    lines = result.strip().split("\n")
    assert lines[1] == 'include "custom_gates.inc";'
    assert 'stdgates.inc' not in result


def test_include_files_multiple():
    """Multiple include files are all emitted in order."""
    includes = ["stdgates.inc", "custom_gates.inc", "extra.inc"]
    emitter = QASM3Emitter(include_files=includes)
    result = emitter.emit(qasm3.loads(SIMPLE_PROGRAM))
    lines = result.strip().split("\n")
    assert lines[0] == "OPENQASM 3.0;"
    assert lines[1] == 'include "stdgates.inc";'
    assert lines[2] == 'include "custom_gates.inc";'
    assert lines[3] == 'include "extra.inc";'
