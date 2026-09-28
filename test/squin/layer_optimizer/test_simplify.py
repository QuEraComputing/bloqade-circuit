import cirq

from bloqade.squin.layer_optimizer.simplify import simplify_diagonals


def _s_count(c: cirq.Circuit) -> int:
    return sum(1 for op in c.all_operations() if op.gate in (cirq.S, cirq.S**-1))


def test_s_then_sdag_through_cz_cancels():
    q = cirq.LineQubit.range(2)
    c = cirq.Circuit([cirq.S(q[0]), cirq.CZ(q[0], q[1]), (cirq.S**-1)(q[0])])
    out = simplify_diagonals(c)
    assert _s_count(out) == 0
    assert cirq.equal_up_to_global_phase(cirq.unitary(c), cirq.unitary(out))


def test_s_then_s_becomes_z():
    q = cirq.LineQubit.range(2)
    c = cirq.Circuit([cirq.S(q[0]), cirq.CZ(q[0], q[1]), cirq.S(q[0])])
    out = simplify_diagonals(c)
    assert _s_count(out) == 0
    assert any(op.gate == cirq.Z for op in out.all_operations())
    assert cirq.equal_up_to_global_phase(cirq.unitary(c), cirq.unitary(out))


def test_axis_gate_blocks_combination():
    q = cirq.LineQubit.range(1)
    c = cirq.Circuit([cirq.S(q[0]), (cirq.X**0.5)(q[0]), cirq.S(q[0])])
    out = simplify_diagonals(c)
    assert _s_count(out) == 2
    assert cirq.equal_up_to_global_phase(cirq.unitary(c), cirq.unitary(out))


def test_preserves_unitary_on_mixed_circuit():
    q = cirq.LineQubit.range(3)
    c = cirq.Circuit(
        [
            cirq.S(q[0]),
            (cirq.Y**0.5)(q[1]),
            cirq.CZ(q[0], q[1]),
            (cirq.S**-1)(q[0]),
            cirq.Z(q[2]),
            cirq.CZ(q[1], q[2]),
            (cirq.X**0.5)(q[0]),
            cirq.S(q[2]),
        ]
    )
    out = simplify_diagonals(c)
    assert cirq.equal_up_to_global_phase(cirq.unitary(c), cirq.unitary(out))
