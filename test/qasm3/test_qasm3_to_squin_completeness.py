"""Parametrized test for QASM3ToSquin conversion completeness.

For any valid QASM3 dialect IR method, after applying QASM3ToSquin,
the resulting IR should contain no QASM3 gate or core dialect statements,
the method's dialect group should be squin.kernel, and the method should
pass verify().

Programs omit measurements since BitReg/Measure are not handled by the
current rewrite rules. This focuses on gate and qubit allocation conversion.
"""

import pytest

from bloqade import qasm3, squin
from bloqade.squin.passes.qasm3_to_squin import QASM3ToSquin
from bloqade.qasm3.dialects.core import stmts as core_stmts
from bloqade.qasm3.dialects.uop import stmts as uop_stmts


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


# --- Representative QASM3 programs (no measurements) ---

QASM3_PROGRAMS_NO_MEASURE = [
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nh q[0];\n',
        id="single-h",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\n'
        "x q[0];\ny q[1];\n",
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
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\n'
        "rx(2.0) q[0];\nry(3.0) q[1];\nrz(0.75) q[2];\n",
        id="rotation-all-angles",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\n'
        "cx q[0], q[1];\n",
        id="two-qubit-cx",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\n'
        "cy q[0], q[1];\ncz q[1], q[2];\n",
        id="two-qubit-cy-cz",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\n'
        "cx q[2], q[0];\ncy q[1], q[2];\ncz q[0], q[1];\n",
        id="two-qubit-mixed",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\n'
        "U(1.5, 0.25, 0.5) q[0];\n",
        id="u-gate-basic",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\n'
        "U(pi, 0.5, 2.0) q[0];\nU(0.1, 3.0, 0.75) q[2];\n",
        id="u-gate-multiple",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[4] q;\n'
        "h q[0];\ncx q[0], q[1];\nrz(0.75) q[2];\ns q[3];\n",
        id="mixed-gates",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[5] q;\n'
        "h q[0];\nx q[1];\nry(pi) q[2];\ncx q[3], q[4];\n"
        "U(0.5, 1.5, 0.25) q[0];\nt q[1];\ncz q[2], q[3];\nrx(0.1) q[4];\n",
        id="mixed-large-circuit",
    ),
    pytest.param(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\n'
        "rx(0.1) q[0];\nry(0.25) q[0];\nrz(0.5) q[0];\n"
        "rx(0.75) q[0];\nry(1.5) q[0];\nrz(2.0) q[0];\n"
        "rx(3.0) q[0];\nry(pi) q[0];\n",
        id="all-angle-values",
    ),
]


@pytest.mark.parametrize("source", QASM3_PROGRAMS_NO_MEASURE)
def test_qasm3_to_squin_conversion_completeness(source: str):
    """Property 2: QASM3ToSquin Conversion Completeness.

    For any valid QASM3 IR method, after applying QASM3ToSquin:
    1. No QASM3 gate or core statements remain in the IR
    2. The method's dialect group is squin.kernel
    3. The method passes verify()

    **Validates: Requirements 4.1, 4.2, 4.3**
    """
    # Parse the QASM3 source into IR
    mt = qasm3.loads(source)
    mt.verify()

    # Run the QASM3ToSquin conversion pass
    QASM3ToSquin(mt.dialects)(mt)

    # 1. No QASM3 gate or core statements should remain
    remaining = [
        stmt
        for stmt in mt.callable_region.walk()
        if isinstance(stmt, QASM3_GATE_AND_CORE_TYPES)
    ]
    assert not remaining, (
        f"QASM3 gate/core statements remain after conversion: "
        f"{[type(s).__name__ for s in remaining]}\n"
        f"Source:\n{source}"
    )

    # 2. Dialects should be squin.kernel
    assert str(mt.dialects) == str(squin.kernel), (
        f"Dialects mismatch after conversion.\n"
        f"Expected: {squin.kernel}\n"
        f"Got: {mt.dialects}"
    )

    # 3. The method should pass verification
    mt.verify()
