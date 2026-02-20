"""Parametrized test for QASM3 emit-parse round trip.

**Property 1: Emit-Parse Round Trip**

For any valid QASM3 dialect IR method containing gates from the Supported_Gate_Set,
emitting the IR to an OpenQASM 3.0 string and then parsing that string back into IR
via loads() SHALL produce a semantically equivalent IR method.

We verify this by checking emit(parse(emit(parse(source)))) == emit(parse(source)),
i.e. the emitted string is stable after one round trip.

**Validates: Requirements 3.1, 3.2, 3.3**
"""

import pytest

from bloqade import qasm3
from bloqade.qasm3.emit import QASM3Emitter


# --- Representative QASM3 programs covering all gate types and combinations ---

QASM3_PROGRAMS = [
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "h q[0];\nc[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="single-h",
    ),
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
        "rz(1.5) q[0];\nrx(0.25) q[1];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="rotation-rz-rx",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\nbit[3] c;\n'
        "rx(2.0) q[0];\nry(3.0) q[1];\nrz(0.75) q[2];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\nc[2] = measure q[2];\n",
        id="rotation-all-angles",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "cx q[0], q[1];\nc[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="two-qubit-cx",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\nbit[3] c;\n'
        "cy q[0], q[1];\ncz q[1], q[2];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\nc[2] = measure q[2];\n",
        id="two-qubit-cy-cz",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\nbit[3] c;\n'
        "cx q[2], q[0];\ncy q[1], q[2];\ncz q[0], q[1];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\nc[2] = measure q[2];\n",
        id="two-qubit-mixed",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "U(1.5, 0.25, 0.5) q[0];\nc[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="u-gate-basic",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\nbit[3] c;\n'
        "U(pi, 0.5, 2.0) q[0];\nU(0.1, 3.0, 0.75) q[2];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\nc[2] = measure q[2];\n",
        id="u-gate-multiple",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[4] q;\nbit[4] c;\n'
        "h q[0];\ncx q[0], q[1];\nrz(0.75) q[2];\ns q[3];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\n"
        "c[2] = measure q[2];\nc[3] = measure q[3];\n",
        id="mixed-gates",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[5] q;\nbit[5] c;\n'
        "h q[0];\nx q[1];\nry(pi) q[2];\ncx q[3], q[4];\nU(0.5, 1.5, 0.25) q[0];\n"
        "t q[1];\ncz q[2], q[3];\nrx(0.1) q[4];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\nc[2] = measure q[2];\n"
        "c[3] = measure q[3];\nc[4] = measure q[4];\n",
        id="mixed-large-circuit",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "h q[0];\nh q[0];\nh q[0];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="repeated-gate",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "h q[0];\nx q[0];\ny q[0];\nz q[0];\ns q[0];\nt q[0];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="all-single-qubit-gates-one-qubit",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "rx(0.1) q[0];\nry(0.25) q[0];\nrz(0.5) q[0];\n"
        "rx(0.75) q[0];\nry(1.5) q[0];\nrz(2.0) q[0];\n"
        "rx(3.0) q[0];\nry(pi) q[0];\n"
        "c[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="all-angle-values",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\n'
        "c[0] = measure q[0];\nc[1] = measure q[1];\n",
        id="measure-only",
    ),
]


@pytest.mark.parametrize("source", QASM3_PROGRAMS)
def test_emit_parse_round_trip(source: str):
    """Property 1: Emit-Parse Round Trip.

    For any valid QASM3 program, emit(parse(emit(parse(source)))) == emit(parse(source)).
    The emitted string must be stable after one round trip through parse and emit.

    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    # First pass: parse -> emit
    mt1 = qasm3.loads(source)
    mt1.verify()
    emitted1 = QASM3Emitter().emit(mt1)

    # Second pass: parse the emitted string -> emit again
    mt2 = qasm3.loads(emitted1)
    mt2.verify()
    emitted2 = QASM3Emitter().emit(mt2)

    # The emitted strings must be identical (round-trip stability)
    assert emitted1 == emitted2, (
        f"Round trip not stable.\n"
        f"First emit:\n{emitted1}\n"
        f"Second emit:\n{emitted2}"
    )
