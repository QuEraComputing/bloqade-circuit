"""Tests that verify the parsed IR structure from qasm3.loads().

Unlike qasm2 which has a plain AST, qasm3.loads() returns a kirin ir.Method.
These tests walk the IR and check that the expected statement types appear
with the correct attributes (register sizes, gate arguments, constant values).
"""

import textwrap
import math

from bloqade import qasm3
from bloqade.qasm3.dialects.core.stmts import (
    QRegNew,
    QRegGet,
    BitRegNew,
    BitRegGet,
    Measure,
    Reset,
)
from bloqade.qasm3.dialects.uop.stmts import (
    H, X, Y, Z, S, T,
    RX, RY, RZ,
    CX, CY, CZ,
    UGate,
)
from bloqade.qasm3.dialects.expr.stmts import ConstInt, ConstFloat, ConstPI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stmts(source: str):
    """Return all IR statements from parsing source."""
    mt = qasm3.loads(source)
    return list(mt.callable_region.walk())


def _typed(source: str, cls):
    """Return only statements of a given type."""
    return [s for s in _stmts(source) if isinstance(s, cls)]


def _const_ints(source: str):
    """Return all ConstInt values in order."""
    return [s.value for s in _typed(source, ConstInt)]


def _const_floats(source: str):
    """Return all ConstFloat values in order."""
    return [s.value for s in _typed(source, ConstFloat)]


# ---------------------------------------------------------------------------
# Register allocation
# ---------------------------------------------------------------------------

BELL_SOURCE = textwrap.dedent("""\
    OPENQASM 3.0;
    qubit[2] q;
    bit[2] c;
    h q[0];
    cx q[0], q[1];
    c[0] = measure q[0];
    c[1] = measure q[1];
""")


def test_bell_has_qreg_and_bitreg():
    """Bell state IR contains exactly one QRegNew and one BitRegNew."""
    assert len(_typed(BELL_SOURCE, QRegNew)) == 1
    assert len(_typed(BELL_SOURCE, BitRegNew)) == 1


def test_bell_register_sizes():
    """QRegNew and BitRegNew are fed size=2 via ConstInt."""
    stmts = _stmts(BELL_SOURCE)
    # First two ConstInts are the register sizes (2, 2)
    sizes = [s.value for s in stmts if isinstance(s, ConstInt)]
    assert sizes[0] == 2  # qubit[2]
    assert sizes[1] == 2  # bit[2]


def test_bell_qreg_get_count():
    """Bell state accesses 5 qubits: q[0] for h, q[0]+q[1] for cx, q[0]+q[1] for measure."""
    assert len(_typed(BELL_SOURCE, QRegGet)) == 5


def test_bell_bitreg_get_count():
    """Bell state accesses 2 bits: c[0] and c[1] for measurements."""
    assert len(_typed(BELL_SOURCE, BitRegGet)) == 2


def test_bell_gates():
    """Bell state has exactly one H and one CX."""
    assert len(_typed(BELL_SOURCE, H)) == 1
    assert len(_typed(BELL_SOURCE, CX)) == 1


def test_bell_measurements():
    """Bell state has exactly two Measure statements."""
    assert len(_typed(BELL_SOURCE, Measure)) == 2


# ---------------------------------------------------------------------------
# Single-qubit gates
# ---------------------------------------------------------------------------

ALL_SINGLE_SOURCE = textwrap.dedent("""\
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[1] q;
    bit[1] c;
    h q[0];
    x q[0];
    y q[0];
    z q[0];
    s q[0];
    t q[0];
    c[0] = measure q[0];
""")


def test_all_single_qubit_gates_present():
    """Each single-qubit gate type appears exactly once."""
    for gate_cls in (H, X, Y, Z, S, T):
        found = _typed(ALL_SINGLE_SOURCE, gate_cls)
        assert len(found) == 1, f"Expected 1 {gate_cls.__name__}, got {len(found)}"


# ---------------------------------------------------------------------------
# Two-qubit controlled gates
# ---------------------------------------------------------------------------

TWO_QUBIT_SOURCE = textwrap.dedent("""\
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[3] q;
    bit[3] c;
    cx q[0], q[1];
    cy q[1], q[2];
    cz q[0], q[2];
    c[0] = measure q[0];
    c[1] = measure q[1];
    c[2] = measure q[2];
""")


def test_two_qubit_gates_present():
    """CX, CY, CZ each appear exactly once."""
    for gate_cls in (CX, CY, CZ):
        found = _typed(TWO_QUBIT_SOURCE, gate_cls)
        assert len(found) == 1, f"Expected 1 {gate_cls.__name__}, got {len(found)}"


# ---------------------------------------------------------------------------
# Rotation gates with constant values
# ---------------------------------------------------------------------------

ROTATION_SOURCE = textwrap.dedent("""\
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[2] q;
    bit[2] c;
    rx(pi) q[0];
    ry(1.5) q[1];
    rz(0.25) q[0];
    c[0] = measure q[0];
    c[1] = measure q[1];
""")


def test_rotation_gates_present():
    """RX, RY, RZ each appear exactly once."""
    assert len(_typed(ROTATION_SOURCE, RX)) == 1
    assert len(_typed(ROTATION_SOURCE, RY)) == 1
    assert len(_typed(ROTATION_SOURCE, RZ)) == 1


def test_rotation_pi_constant():
    """rx(pi) produces a ConstPI in the IR."""
    assert len(_typed(ROTATION_SOURCE, ConstPI)) == 1


def test_rotation_float_constants():
    """ry(1.5) and rz(0.25) produce ConstFloat values."""
    floats = _const_floats(ROTATION_SOURCE)
    assert 1.5 in floats
    assert 0.25 in floats


# ---------------------------------------------------------------------------
# U gate
# ---------------------------------------------------------------------------

UGATE_SOURCE = textwrap.dedent("""\
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[1] q;
    bit[1] c;
    U(pi, 1.5, 0.25) q[0];
    c[0] = measure q[0];
""")


def test_ugate_present():
    """U(pi, 1.5, 0.25) produces exactly one UGate statement."""
    assert len(_typed(UGATE_SOURCE, UGate)) == 1


def test_ugate_has_pi():
    """U(pi, ...) produces a ConstPI."""
    assert len(_typed(UGATE_SOURCE, ConstPI)) == 1


def test_ugate_float_params():
    """U(..., 1.5, 0.25) produces ConstFloat values for phi and lam."""
    floats = _const_floats(UGATE_SOURCE)
    assert 1.5 in floats
    assert 0.25 in floats


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

RESET_SOURCE = textwrap.dedent("""\
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[1] q;
    bit[1] c;
    h q[0];
    reset q[0];
    c[0] = measure q[0];
""")


def test_reset_present():
    """reset q[0] produces exactly one Reset statement."""
    assert len(_typed(RESET_SOURCE, Reset)) == 1


def test_reset_with_h_and_measure():
    """Program with reset also has H and Measure."""
    assert len(_typed(RESET_SOURCE, H)) == 1
    assert len(_typed(RESET_SOURCE, Measure)) == 1


# ---------------------------------------------------------------------------
# Larger mixed program
# ---------------------------------------------------------------------------

MIXED_SOURCE = textwrap.dedent("""\
    OPENQASM 3.0;
    include "stdgates.inc";
    qubit[3] q;
    bit[3] c;
    h q[0];
    x q[1];
    rx(pi) q[2];
    cx q[0], q[1];
    U(0.5, 1.5, 0.25) q[0];
    reset q[2];
    c[0] = measure q[0];
    c[1] = measure q[1];
    c[2] = measure q[2];
""")


def test_mixed_gate_counts():
    """Mixed program has the right count of each gate type."""
    assert len(_typed(MIXED_SOURCE, H)) == 1
    assert len(_typed(MIXED_SOURCE, X)) == 1
    assert len(_typed(MIXED_SOURCE, RX)) == 1
    assert len(_typed(MIXED_SOURCE, CX)) == 1
    assert len(_typed(MIXED_SOURCE, UGate)) == 1
    assert len(_typed(MIXED_SOURCE, Reset)) == 1
    assert len(_typed(MIXED_SOURCE, Measure)) == 3


def test_mixed_register_sizes():
    """Mixed program allocates qubit[3] and bit[3]."""
    ints = _const_ints(MIXED_SOURCE)
    # First two ConstInts are register sizes
    assert ints[0] == 3
    assert ints[1] == 3


def test_mixed_no_unexpected_gates():
    """Mixed program has no Y, Z, S, T, RY, RZ, CY, CZ."""
    for cls in (Y, Z, S, T, RY, RZ, CY, CZ):
        assert len(_typed(MIXED_SOURCE, cls)) == 0, f"Unexpected {cls.__name__}"


# ---------------------------------------------------------------------------
# Measure-only program
# ---------------------------------------------------------------------------

MEASURE_ONLY_SOURCE = textwrap.dedent("""\
    OPENQASM 3.0;
    qubit[2] q;
    bit[2] c;
    c[0] = measure q[0];
    c[1] = measure q[1];
""")


def test_measure_only_no_gates():
    """A measure-only program has no gate statements."""
    for cls in (H, X, Y, Z, S, T, RX, RY, RZ, CX, CY, CZ, UGate):
        assert len(_typed(MEASURE_ONLY_SOURCE, cls)) == 0


def test_measure_only_has_measures():
    """A measure-only program still has Measure statements."""
    assert len(_typed(MEASURE_ONLY_SOURCE, Measure)) == 2
