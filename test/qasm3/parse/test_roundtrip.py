"""Round-trip tests for QASM3: parse → emit → parse → emit, check stability."""

import pathlib

from bloqade import qasm3
from bloqade.qasm3.emit import QASM3Emitter


def _roundtrip(source: str) -> bool:
    """Parse source, emit, parse again, emit again — check strings match."""
    emitter = QASM3Emitter()
    mt1 = qasm3.loads(source)
    out1 = emitter.emit(mt1)
    mt2 = qasm3.loads(out1)
    out2 = emitter.emit(mt2)
    return out1 == out2


def _roundtrip_file(path: pathlib.Path) -> bool:
    """Same as _roundtrip but reads from a .qasm file."""
    mt1 = qasm3.loadfile(path)
    emitter = QASM3Emitter()
    out1 = emitter.emit(mt1)
    mt2 = qasm3.loads(out1)
    out2 = emitter.emit(mt2)
    return out1 == out2


# ---------------------------------------------------------------------------
# File-based round-trips (programs/ directory)
# ---------------------------------------------------------------------------

PROGRAMS_DIR = pathlib.Path(__file__).parent / "programs"


def test_roundtrip_all_program_files():
    """Every .qasm file in programs/ survives a parse-emit-parse-emit cycle."""
    files = sorted(PROGRAMS_DIR.glob("*.qasm"))
    assert files, "No .qasm files found in programs/"
    for f in files:
        assert _roundtrip_file(f), f"Round-trip failed for {f.name}"


# ---------------------------------------------------------------------------
# Inline round-trips
# ---------------------------------------------------------------------------


def test_roundtrip_bell():
    src = (
        "OPENQASM 3.0;\n"
        "qubit[2] q;\n"
        "bit[2] c;\n"
        "h q[0];\n"
        "cx q[0], q[1];\n"
        "c[0] = measure q[0];\n"
        "c[1] = measure q[1];\n"
    )
    assert _roundtrip(src)


def test_roundtrip_rotations():
    src = (
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "qubit[1] q;\nbit[1] c;\n"
        "rx(pi) q[0];\nry(0.5) q[0];\nrz(0.25) q[0];\n"
        "c[0] = measure q[0];\n"
    )
    assert _roundtrip(src)


def test_roundtrip_u_gate():
    src = (
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "qubit[1] q;\nbit[1] c;\n"
        "U(1.5, 0.25, 0.5) q[0];\n"
        "c[0] = measure q[0];\n"
    )
    assert _roundtrip(src)


def test_roundtrip_reset():
    src = (
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "qubit[1] q;\nbit[1] c;\n"
        "h q[0];\nreset q[0];\n"
        "c[0] = measure q[0];\n"
    )
    assert _roundtrip(src)


def test_roundtrip_measure_only():
    src = (
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "qubit[2] q;\nbit[2] c;\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\n"
    )
    assert _roundtrip(src)
