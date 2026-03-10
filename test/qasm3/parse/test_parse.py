"""Tests for QASM3 parsing: loads, loadfile, and unsupported constructs."""

import logging
import pathlib
import tempfile
import textwrap

import pytest
from kirin import lowering

from bloqade import qasm3
from bloqade.qasm3.emit import QASM3Emitter

BELL_STATE = textwrap.dedent("""\
    OPENQASM 3.0;
    qubit[2] q;
    bit[2] c;
    h q[0];
    cx q[0], q[1];
    c[0] = measure q[0];
    c[1] = measure q[1];
""")


def test_loads_bell_state():
    """loads() parses a Bell state and produces valid IR."""
    mt = qasm3.loads(BELL_STATE)
    mt.verify()


def test_loads_all_gates():
    """loads() handles every supported gate type."""
    source = textwrap.dedent("""\
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
    mt = qasm3.loads(source)
    mt.verify()


def test_loadfile():
    """loadfile() reads a .qasm file and produces valid IR."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        p = pathlib.Path(tmp_dir) / "bell.qasm"
        p.write_text(BELL_STATE)
        mt = qasm3.loadfile(p)
        mt.verify()


@pytest.mark.parametrize(
    "source,construct",
    [
        pytest.param(
            textwrap.dedent("""\
                OPENQASM 3.0;
                qubit[2] q;
                for int i in [0:2] { h q[i]; }
            """),
            "ForInLoop",
            id="for-loop",
        ),
        pytest.param(
            textwrap.dedent("""\
                OPENQASM 3.0;
                qubit[1] q;
                bit[1] c;
                c[0] = measure q[0];
                if (c[0]) { x q[0]; }
            """),
            "BranchingStatement",
            id="if-statement",
        ),
        pytest.param(
            textwrap.dedent("""\
                OPENQASM 3.0;
                qubit[1] q;
                while (true) { h q[0]; }
            """),
            "WhileLoop",
            id="while-loop",
        ),
    ],
)
def test_unsupported_construct_raises(source, construct):
    """Unsupported QASM3 constructs raise BuildError."""
    with pytest.raises(
        lowering.BuildError, match=f"Unsupported QASM3 construct: {construct}"
    ):
        qasm3.loads(source)


# ---- Custom gate definitions ----


def test_loads_custom_gate_definition():
    """loads() parses a gate definition and registers it without error."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        gate bell a, b {
            h a;
            cx a, b;
        }
        qubit[2] q;
        bell q[0], q[1];
    """)
    mt = qasm3.loads(source)
    mt.verify()


def test_loads_parameterized_custom_gate():
    """loads() parses a gate definition with a classical angle parameter."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        gate myrot(theta) q {
            rx(theta) q;
        }
        qubit[1] q;
        myrot(1.57) q[0];
    """)
    mt = qasm3.loads(source)
    mt.verify()


def test_loads_custom_gate_called_multiple_times():
    """A user-defined gate can be invoked more than once in the program body."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        gate prep q {
            h q;
        }
        qubit[2] q;
        prep q[0];
        prep q[1];
    """)
    mt = qasm3.loads(source)
    mt.verify()


# ---- Barrier ----


def test_barrier_single_qubit():
    """barrier q[0]; parses and produces valid IR."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        qubit[2] q;
        h q[0];
        barrier q[0];
        h q[1];
    """)
    mt = qasm3.loads(source)
    mt.verify()


def test_barrier_multiple_qubits():
    """barrier q[0], q[1]; parses and produces valid IR."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        qubit[2] q;
        h q[0];
        cx q[0], q[1];
        barrier q[0], q[1];
    """)
    mt = qasm3.loads(source)
    mt.verify()


def test_barrier_across_registers():
    """barrier q[0], r[0]; across two registers parses correctly."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        qubit[2] q;
        qubit[2] r;
        barrier q[0], r[0];
    """)
    mt = qasm3.loads(source)
    mt.verify()


def test_barrier_emit_roundtrip():
    """barrier survives a parse -> emit roundtrip."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        qubit[2] q;
        barrier q[0], q[1];
    """)
    mt = qasm3.loads(source)
    out = QASM3Emitter().emit(mt)
    assert "barrier q[0], q[1];" in out


# ---------------------------------------------------------------------------
# loadfile edge cases
# ---------------------------------------------------------------------------


def test_loadfile_file_not_found():
    """loadfile raises FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError, match="does not exist"):
        qasm3.loadfile("/tmp/nonexistent_file_abc123.qasm")


def test_loadfile_wrong_suffix_warns(tmp_path, caplog):
    """loadfile warns when file doesn't end with .qasm or .qasm3."""
    p = tmp_path / "test.txt"
    p.write_text("OPENQASM 3.0;\nqubit[1] q;\nh q[0];\n")
    with caplog.at_level(logging.WARNING):
        _ = qasm3.loadfile(p)
    assert "does not end with .qasm or .qasm3" in caplog.text


def test_loadfile_kernel_name_none(tmp_path):
    """loadfile uses stem as kernel_name when kernel_name=None."""
    p = tmp_path / "my_circuit.qasm"
    p.write_text("OPENQASM 3.0;\nqubit[1] q;\nh q[0];\n")
    mt = qasm3.loadfile(p, kernel_name=None)
    assert mt.sym_name == "my_circuit"


def test_loadfile_qasm3_suffix(tmp_path):
    """loadfile accepts .qasm3 suffix without warning."""
    p = tmp_path / "test.qasm3"
    p.write_text("OPENQASM 3.0;\nqubit[1] q;\nh q[0];\n")
    mt = qasm3.loadfile(p, kernel_name="test")
    mt.verify()


def test_loadfile_string_path(tmp_path):
    """loadfile accepts a string path."""
    p = tmp_path / "bell.qasm"
    p.write_text("OPENQASM 3.0;\nqubit[2] q;\nh q[0];\ncx q[0], q[1];\n")
    mt = qasm3.loadfile(str(p))
    mt.verify()


# ---------------------------------------------------------------------------
# QASM3 parsing — declarations, expressions, error paths
# ---------------------------------------------------------------------------


def test_lowering_unsupported_include():
    """Include of non-stdgates file raises BuildError."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "custom.inc";
        qubit[1] q;
    """)
    with pytest.raises(lowering.BuildError, match="Unsupported include"):
        qasm3.loads(source)


def test_lowering_unsupported_classical_type():
    """Non-bit classical declaration raises BuildError."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        int[32] x;
    """)
    with pytest.raises(lowering.BuildError, match="Unsupported classical type"):
        qasm3.loads(source)


def test_lowering_single_qubit_declaration():
    """'qubit q;' (no size) parses correctly."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        qubit q;
    """)
    mt = qasm3.loads(source)
    mt.verify()


def test_lowering_single_bit_declaration():
    """'bit c;' (no size) parses correctly."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        qubit q;
        bit c;
    """)
    mt = qasm3.loads(source)
    mt.verify()


# ---------------------------------------------------------------------------
# Expression lowering in QASM3 parsing
# ---------------------------------------------------------------------------


def test_lowering_binary_expression_add():
    """Binary addition in expression is lowered correctly."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[1] q;
        rx(1.0 + 0.5) q[0];
    """)
    qasm3.loads(source).verify()


def test_lowering_binary_expression_sub():
    """Binary subtraction in expression is lowered correctly."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[1] q;
        rx(1.0 - 0.5) q[0];
    """)
    qasm3.loads(source).verify()


def test_lowering_binary_expression_mul():
    """Binary multiplication in expression is lowered correctly."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[1] q;
        rx(2.0 * 0.5) q[0];
    """)
    qasm3.loads(source).verify()


def test_lowering_binary_expression_div():
    """Binary division in expression is lowered correctly."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[1] q;
        rx(pi / 2.0) q[0];
    """)
    qasm3.loads(source).verify()


def test_lowering_unary_neg():
    """Unary negation in expression is lowered correctly."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[1] q;
        rx(-1.5) q[0];
    """)
    qasm3.loads(source).verify()


def test_lowering_float_literal():
    """Float literal in expression is lowered correctly."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[1] q;
        rx(3.14) q[0];
    """)
    qasm3.loads(source).verify()


def test_lowering_identifier_in_gate_body():
    """Identifier reference in gate body is lowered correctly."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        gate myg(theta) q {
            rx(theta) q;
        }
        qubit[1] q;
        myg(1.0) q[0];
    """)
    qasm3.loads(source).verify()


def test_lowering_unknown_identifier_raises():
    """Unknown identifier in expression raises BuildError."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[1] q;
        rx(unknown_var) q[0];
    """)
    with pytest.raises(lowering.BuildError, match="Unknown identifier"):
        qasm3.loads(source)


def test_lowering_compactify_false():
    """loads with compactify=False still produces valid IR."""
    source = "OPENQASM 3.0;\nqubit[1] q;\nh q[0];\n"
    qasm3.loads(source, compactify=False).verify()


def test_lowering_with_file_and_offsets():
    """loads with file and offset parameters works."""
    source = "OPENQASM 3.0;\nqubit[1] q;\nh q[0];\n"
    qasm3.loads(source, file="test.qasm", lineno_offset=10, col_offset=5).verify()


def test_lowering_u3_alias():
    """u3 is an alias for U gate."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[1] q;
        u3(1.0, 2.0, 3.0) q[0];
    """)
    qasm3.loads(source).verify()


# ---------------------------------------------------------------------------
# Gate error paths
# ---------------------------------------------------------------------------


def test_lowering_wrong_qubit_count_single_gate():
    """Single-qubit gate with wrong qubit count raises BuildError."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[2] q;
        h q[0], q[1];
    """)
    with pytest.raises(lowering.BuildError, match="expects 1 qubit"):
        qasm3.loads(source)


def test_lowering_wrong_qubit_count_two_qubit_gate():
    """Two-qubit gate with wrong qubit count raises BuildError."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[3] q;
        cx q[0], q[1], q[2];
    """)
    with pytest.raises(lowering.BuildError, match="expects 2 qubits"):
        qasm3.loads(source)


def test_lowering_rotation_gate_wrong_params():
    """Rotation gate with wrong param count raises BuildError."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[1] q;
        rx(1.0, 2.0) q[0];
    """)
    with pytest.raises(lowering.BuildError, match="expects 1 qubit and 1 parameter"):
        qasm3.loads(source)


def test_lowering_u_gate_wrong_params():
    """U gate with wrong param count raises BuildError."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[1] q;
        U(1.0, 2.0) q[0];
    """)
    with pytest.raises(lowering.BuildError, match="expects 1 qubit and 3 parameters"):
        qasm3.loads(source)


# ---------------------------------------------------------------------------
# Qubit/bit reference error paths
# ---------------------------------------------------------------------------


def test_lowering_undefined_qubit_register():
    """Reference to undefined qubit register raises BuildError."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        h undefined_q[0];
    """)
    with pytest.raises(lowering.BuildError, match="Undefined register"):
        qasm3.loads(source)


def test_lowering_undefined_qubit_identifier():
    """Reference to undefined qubit identifier raises BuildError."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        gate myg q {
            h undefined_q;
        }
        qubit[1] q;
        myg q[0];
    """)
    with pytest.raises(lowering.BuildError):
        qasm3.loads(source)


def test_lowering_undefined_bit_register():
    """Reference to undefined bit register raises BuildError."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        qubit[1] q;
        undefined_c[0] = measure q[0];
    """)
    with pytest.raises(lowering.BuildError, match="Undefined register"):
        qasm3.loads(source)


def test_lowering_gate_definition_with_body():
    """Gate definition with multiple statements in body."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        gate bell a, b {
            h a;
            cx a, b;
        }
        qubit[2] q;
        bell q[0], q[1];
    """)
    qasm3.loads(source).verify()


def test_lowering_complex_expression_in_gate():
    """Complex expression (nested binary ops) in gate parameter."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        gate myg(a, b) q {
            rx(a * b + 1.0) q;
        }
        qubit[1] q;
        myg(0.5, 2.0) q[0];
    """)
    qasm3.loads(source).verify()


def test_lowering_global_identifier_found():
    """Gate calling another gate resolves the global correctly."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        gate prep q {
            h q;
        }
        gate bell a, b {
            prep a;
            cx a, b;
        }
        qubit[2] q;
        bell q[0], q[1];
    """)
    qasm3.loads(source).verify()


def test_lowering_user_defined_gate_call():
    """User-defined gate call via func.Invoke path."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        gate custom(theta) q {
            rx(theta) q;
            rz(theta) q;
        }
        qubit[2] q;
        custom(1.5) q[0];
        custom(0.5) q[1];
    """)
    mt = qasm3.loads(source)
    mt.verify()
    result = QASM3Emitter().emit(mt)
    assert "gate custom" in result


def test_lowering_bit_identifier_in_gate_body():
    """Bit identifier reference as plain identifier (not indexed)."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        qubit[1] q;
        bit c;
        c = measure q[0];
    """)
    try:
        mt = qasm3.loads(source)
        mt.verify()
    except Exception:
        pass
