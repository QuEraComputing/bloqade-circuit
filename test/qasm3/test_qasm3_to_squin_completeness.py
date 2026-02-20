"""Property test for QASM3ToSquin conversion completeness.

**Property 2: QASM3ToSquin Conversion Completeness**

For any valid QASM3 dialect IR method, after applying QASM3ToSquin,
the resulting IR SHALL contain no QASM3 gate or core dialect statements,
the method's dialect group SHALL be squin.kernel, and the method SHALL
pass verify().

We generate random QASM3 programs (without measurements, since BitReg/Measure
are not handled by the current rewrite rules), run QASM3ToSquin, and verify
that all QASM3 gate and core statements have been converted to squin equivalents.

**Validates: Requirements 4.1, 4.2, 4.3**
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from bloqade import qasm3, squin
from bloqade.squin.passes.qasm3_to_squin import QASM3ToSquin
from bloqade.qasm3.dialects.core import stmts as core_stmts
from bloqade.qasm3.dialects.uop import stmts as uop_stmts


# All QASM3 gate and core statement types that MUST be fully converted
QASM3_GATE_AND_CORE_TYPES = (
    # Core statements
    core_stmts.QRegNew,
    core_stmts.QRegGet,
    core_stmts.Reset,
    # UOp gate statements
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


# --- Strategies for generating random QASM3 programs ---

angle_strategy = st.sampled_from(
    ["pi", "1.5", "0.25", "0.5", "2.0", "3.0", "0.1", "0.75"]
)

SINGLE_QUBIT_GATES = ["h", "x", "y", "z", "s", "t"]
ROTATION_GATES = ["rx", "ry", "rz"]
TWO_QUBIT_GATES = ["cx", "cy", "cz"]


@st.composite
def qasm3_gate_line(draw, n_qubits: int):
    """Generate a single random gate application line."""
    gate_type = draw(st.sampled_from(["single", "rotation", "two_qubit", "u_gate"]))

    if gate_type == "single":
        gate = draw(st.sampled_from(SINGLE_QUBIT_GATES))
        idx = draw(st.integers(min_value=0, max_value=n_qubits - 1))
        return f"{gate} q[{idx}];"

    elif gate_type == "rotation":
        gate = draw(st.sampled_from(ROTATION_GATES))
        angle = draw(angle_strategy)
        idx = draw(st.integers(min_value=0, max_value=n_qubits - 1))
        return f"{gate}({angle}) q[{idx}];"

    elif gate_type == "two_qubit":
        assume(n_qubits >= 2)
        gate = draw(st.sampled_from(TWO_QUBIT_GATES))
        ctrl = draw(st.integers(min_value=0, max_value=n_qubits - 1))
        targ = draw(
            st.integers(min_value=0, max_value=n_qubits - 1).filter(
                lambda x: x != ctrl
            )
        )
        return f"{gate} q[{ctrl}], q[{targ}];"

    else:  # u_gate
        theta = draw(angle_strategy)
        phi = draw(angle_strategy)
        lam = draw(angle_strategy)
        idx = draw(st.integers(min_value=0, max_value=n_qubits - 1))
        return f"U({theta}, {phi}, {lam}) q[{idx}];"


@st.composite
def qasm3_program_no_measure(draw):
    """Generate a random valid QASM3 program without measurements.

    We omit measurements because BitReg/Measure are not handled by the
    current QASM3ToSquin rewrite rules. This focuses the property test
    on gate and qubit allocation conversion completeness.
    """
    n_qubits = draw(st.integers(min_value=2, max_value=5))
    n_gates = draw(st.integers(min_value=1, max_value=10))

    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        f"qubit[{n_qubits}] q;",
    ]

    for _ in range(n_gates):
        gate_line = draw(qasm3_gate_line(n_qubits))
        lines.append(gate_line)

    return "\n".join(lines) + "\n"


@given(source=qasm3_program_no_measure())
@settings(max_examples=100, deadline=None)
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
