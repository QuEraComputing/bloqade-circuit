"""Tests for the QASM3ToSquin conversion pass."""

import textwrap

import pytest

from bloqade import qasm3, squin
from bloqade.squin.passes import QASM3ToSquin
from bloqade.qasm3.dialects.uop import stmts as uop_stmts
from bloqade.qasm3.dialects.core import stmts as core_stmts

# All QASM3 gate and core statement types that MUST be fully converted
QASM3_GATE_AND_CORE_TYPES = (
    core_stmts.QRegNew,
    core_stmts.QRegGet,
    core_stmts.Reset,
    uop_stmts.H,
    uop_stmts.X,
    uop_stmts.Y,
    uop_stmts.Z,
    uop_stmts.S,
    uop_stmts.T,
    uop_stmts.RX,
    uop_stmts.RY,
    uop_stmts.RZ,
    uop_stmts.CX,
    uop_stmts.CY,
    uop_stmts.CZ,
    uop_stmts.UGate,
)


# ---------------------------------------------------------------------------
# Conversion completeness (parametrized)
# ---------------------------------------------------------------------------

QASM3_PROGRAMS_NO_MEASURE = [
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nh q[0];\n',
        id="single-h",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\n' "x q[0];\ny q[1];\n",
        id="single-x-y",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\n'
        "z q[0];\ns q[1];\nt q[2];\n",
        id="single-z-s-t",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\n'
        "h q[0];\nx q[0];\ny q[0];\nz q[0];\ns q[0];\nt q[0];\n",
        id="all-single-qubit-gates",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\n'
        "rx(pi) q[0];\nry(0.5) q[1];\n",
        id="rotation-rx-ry",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\n'
        "rz(1.5) q[0];\nrx(0.25) q[1];\n",
        id="rotation-rz-rx",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\n' "cx q[0], q[1];\n",
        id="two-qubit-cx",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\n'
        "cy q[0], q[1];\ncz q[1], q[2];\n",
        id="two-qubit-cy-cz",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\n'
        "U(1.5, 0.25, 0.5) q[0];\n",
        id="u-gate",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[4] q;\n'
        "h q[0];\ncx q[0], q[1];\nrz(0.75) q[2];\ns q[3];\n",
        id="mixed-gates",
    ),
]


@pytest.mark.parametrize("source", QASM3_PROGRAMS_NO_MEASURE)
def test_conversion_completeness(source: str):
    """After QASM3ToSquin: no qasm3 gate/core stmts remain, dialects == squin.kernel, verify passes."""
    mt = qasm3.loads(source)
    mt.verify()

    QASM3ToSquin(mt.dialects)(mt)

    remaining = [
        stmt
        for stmt in mt.callable_region.walk()
        if isinstance(stmt, QASM3_GATE_AND_CORE_TYPES)
    ]
    assert (
        not remaining
    ), f"QASM3 statements remain: {[type(s).__name__ for s in remaining]}"
    assert str(mt.dialects) == str(squin.kernel)
    mt.verify()


# ---------------------------------------------------------------------------
# End-to-end: load → convert → verify
# ---------------------------------------------------------------------------


def test_bell_state_e2e():
    """Load Bell state QASM3, convert to squin, verify."""
    source = textwrap.dedent("""\
        OPENQASM 3.0;
        qubit[2] q;
        bit[2] c;
        h q[0];
        cx q[0], q[1];
        c[0] = measure q[0];
        c[1] = measure q[1];
    """)
    mt = qasm3.loads(source)
    mt.verify()
    QASM3ToSquin(dialects=mt.dialects)(mt)
    mt.verify()


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
def test_each_gate_converts(gate_line):
    """Each supported gate loads and converts to squin."""
    source = textwrap.dedent(f"""\
        OPENQASM 3.0;
        include "stdgates.inc";
        qubit[2] q;
        {gate_line}
    """)
    mt = qasm3.loads(source)
    mt.verify()
    QASM3ToSquin(dialects=mt.dialects)(mt)
    mt.verify()
