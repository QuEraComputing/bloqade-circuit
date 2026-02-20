"""End-to-end unit tests for the QASM3 workflow.

Tests:
- Loading a Bell state QASM3 program, converting to squin, verifying result
- Unsupported constructs raise BuildError
- One example per gate type in Supported_Gate_Set

Requirements: 1.1, 1.4, 4.1, 5.1, 5.3
"""

import textwrap

import pytest
from kirin import lowering

from bloqade import qasm3
from bloqade.squin.passes import QASM3ToSquin


# --- Bell state end-to-end ---


BELL_STATE = textwrap.dedent("""\
    OPENQASM 3.0;
    qubit[2] q;
    bit[2] c;
    h q[0];
    cx q[0], q[1];
    c[0] = measure q[0];
    c[1] = measure q[1];
""")


def test_bell_state_e2e_loads_converts_verifies():
    """Load Bell state, convert to squin, verify IR is valid."""
    mt = qasm3.loads(BELL_STATE)
    mt.verify()
    QASM3ToSquin(dialects=mt.dialects)(mt)
    # After conversion the IR should still be valid
    mt.verify()


# --- Unsupported constructs ---


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
    with pytest.raises(lowering.BuildError, match=f"Unsupported QASM3 construct: {construct}"):
        qasm3.loads(source)


# --- One example per gate type in Supported_Gate_Set ---


def _loads_and_converts(source: str):
    """Helper: load QASM3 source, convert to squin, verify."""
    mt = qasm3.loads(source)
    mt.verify()
    QASM3ToSquin(dialects=mt.dialects)(mt)
    mt.verify()
    return mt


@pytest.mark.parametrize(
    "gate_line",
    [
        pytest.param("h q[0];", id="H"),
        pytest.param("x q[0];", id="X"),
        pytest.param("y q[0];", id="Y"),
        pytest.param("z q[0];", id="Z"),
        pytest.param("s q[0];", id="S"),
        pytest.param("t q[0];", id="T"),
        pytest.param("rx(1.5) q[0];", id="RX"),
        pytest.param("ry(1.5) q[0];", id="RY"),
        pytest.param("rz(1.5) q[0];", id="RZ"),
        pytest.param("cx q[0], q[1];", id="CX"),
        pytest.param("cy q[0], q[1];", id="CY"),
        pytest.param("cz q[0], q[1];", id="CZ"),
        pytest.param("U(1.5, 0.5, 0.25) q[0];", id="U3"),
    ],
)
def test_gate_loads_and_converts(gate_line):
    """Each gate in Supported_Gate_Set loads and converts to squin."""
    source = textwrap.dedent(f"""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[2] q;
        {gate_line}
    """)
    _loads_and_converts(source)
