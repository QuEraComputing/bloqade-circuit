"""Checkpoint test: verify QASM3 parsing produces valid IR."""

import textwrap

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


def test_bell_state_loads_and_verifies():
    """Load a Bell state QASM3 program and verify the IR is valid."""
    mt = qasm3.loads(BELL_STATE)
    # loads() already calls mt.verify() internally, but call it again
    # explicitly to confirm the returned IR is valid
    mt.verify()
    mt.print()
