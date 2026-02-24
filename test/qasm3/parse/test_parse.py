"""Tests for QASM3 parsing: loads, loadfile, and unsupported constructs."""

import textwrap
import pathlib
import tempfile

import pytest
from kirin import lowering

from bloqade import qasm3


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
