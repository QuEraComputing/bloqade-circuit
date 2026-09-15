import cirq

from bloqade.squin import gate
from bloqade.cirq_utils import emit_circuit, load_circuit
from bloqade.squin.passes.clifford_normalize import CliffordNormalize


def _stmt_count(mt, cls):
    return sum(1 for s in mt.callable_region.blocks[0].stmts if isinstance(s, cls))


def test_normalize_preserves_unitary():
    q = cirq.LineQubit.range(3)
    circuit = cirq.Circuit(
        cirq.H(q[0]),
        cirq.X(q[1]),
        (cirq.Y**0.5)(q[2]),
        cirq.CZ(q[0], q[1]),
        cirq.CZ(q[1], q[2]),
        (cirq.X**0.5)(q[0]),
        cirq.S(q[1]) ** -1,
        cirq.H(q[2]),
    )
    u_before = cirq.unitary(circuit)

    mt = load_circuit(circuit)
    CliffordNormalize(mt.dialects)(mt)
    u_after = cirq.unitary(emit_circuit(mt))

    assert cirq.equal_up_to_global_phase(u_before, u_after)


def test_normalize_eliminates_phasedxz_for_cliffords():
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.PhasedXZGate(x_exponent=0.5, z_exponent=0.5, axis_phase_exponent=0.0).on(
            q[0]
        ),
        cirq.CZ(q[0], q[1]),
    )

    mt = load_circuit(circuit)
    CliffordNormalize(mt.dialects)(mt)

    assert _stmt_count(mt, gate.stmts.PhasedXZ) == 0


def test_normalize_emits_only_sqrt_x_s_pauli_cz():
    """Body should contain only {SqrtX, SqrtY, S, X, Y, Z, ControlledGate}."""
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.H(q[0]),
        cirq.X(q[1]),
        cirq.CZ(q[0], q[1]),
        (cirq.X**0.5)(q[0]),
        (cirq.Y**0.5)(q[1]),
    )

    mt = load_circuit(circuit)
    CliffordNormalize(mt.dialects)(mt)

    allowed = (
        gate.stmts.SqrtX,
        gate.stmts.SqrtY,
        gate.stmts.S,
        gate.stmts.X,
        gate.stmts.Y,
        gate.stmts.Z,
        gate.stmts.ControlledGate,
    )
    for s in mt.callable_region.blocks[0].stmts:
        if isinstance(s, gate.stmts.Gate):
            assert isinstance(s, allowed), f"unexpected stmt: {type(s).__name__}"


def test_normalize_handles_empty_circuit():
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.CZ(q[0], q[1]))
    mt = load_circuit(circuit)
    CliffordNormalize(mt.dialects)(mt)
    assert _stmt_count(mt, gate.stmts.ControlledGate) == 1
