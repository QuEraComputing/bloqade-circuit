"""Property test for QASM3 emit-parse round trip.

**Property 1: Emit-Parse Round Trip**

For any valid QASM3 dialect IR method containing gates from the Supported_Gate_Set,
emitting the IR to an OpenQASM 3.0 string and then parsing that string back into IR
via loads() SHALL produce a semantically equivalent IR method.

We verify this by checking emit(parse(emit(parse(source)))) == emit(parse(source)),
i.e. the emitted string is stable after one round trip.

**Validates: Requirements 3.1, 3.2, 3.3**
"""

import math

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from bloqade import qasm3
from bloqade.qasm3.emit import QASM3Emitter


# --- Strategies for generating random QASM3 programs ---

# Angle values that survive float round-tripping cleanly
angle_strategy = st.sampled_from(
    [
        "pi",
        "1.5",
        "0.25",
        "0.5",
        "2.0",
        "3.0",
        "0.1",
        "0.75",
    ]
)

SINGLE_QUBIT_GATES = ["h", "x", "y", "z", "s", "t"]
ROTATION_GATES = ["rx", "ry", "rz"]
TWO_QUBIT_GATES = ["cx", "cy", "cz"]



@st.composite
def qasm3_gate_line(draw, n_qubits: int):
    """Generate a single random gate application line for a QASM3 program."""
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
def qasm3_program(draw):
    """Generate a random valid QASM3 program string."""
    n_qubits = draw(st.integers(min_value=2, max_value=5))
    n_gates = draw(st.integers(min_value=1, max_value=10))

    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        f"qubit[{n_qubits}] q;",
        f"bit[{n_qubits}] c;",
    ]

    for _ in range(n_gates):
        gate_line = draw(qasm3_gate_line(n_qubits))
        lines.append(gate_line)

    # Add measurements for all qubits
    for i in range(n_qubits):
        lines.append(f"c[{i}] = measure q[{i}];")

    return "\n".join(lines) + "\n"


@given(source=qasm3_program())
@settings(max_examples=100, deadline=None)
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
