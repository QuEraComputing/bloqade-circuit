import itertools

import cirq

from bloqade.squin.layer_optimizer.schedule import apply_schedule, extract_layers
from bloqade.squin.passes.clifford_normalize import (
    _normalize,
    _eject_paulis_through_primitives,
)


def _normalized(circuit):
    return _normalize(circuit)


def test_extract_layers_axis_and_gaps():
    q = cirq.LineQubit.range(2)
    c = _normalized(
        cirq.Circuit(
            (cirq.X**0.5)(q[0]),
            cirq.CZ(q[0], q[1]),
            (cirq.X**0.5)(q[1]),
        )
    )
    layer_data, s_qubits, qubits = extract_layers(c)
    # One CZ -> two gaps, all lists aligned.
    assert len(layer_data) == 2
    assert len(s_qubits) == 2
    assert len(qubits) == 2
    # Axes are 'X' or 'Y'.
    for gap in layer_data:
        assert all(ax in ("X", "Y") for ax in gap.values())


def test_apply_schedule_all_zero_is_noop_unitary():
    q = cirq.LineQubit.range(2)
    c = _normalized(
        cirq.Circuit(
            (cirq.X**0.5)(q[0]),
            cirq.CZ(q[0], q[1]),
            (cirq.Y**0.5)(q[1]),
        )
    )
    layer_data, _, qubits = extract_layers(c)
    schedule = [{qq: 0 for qq in qubits} for _ in range(len(layer_data) + 1)]
    out = _eject_paulis_through_primitives(apply_schedule(c, schedule))
    assert cirq.equal_up_to_global_phase(cirq.unitary(c), cirq.unitary(out))


def test_apply_schedule_exhaustive_preserves_unitary():
    """Every binary schedule must preserve the unitary (up to global phase).

    Cirq op-space, so we normalize once and reuse — no per-schedule IR
    round-trip.
    """
    q = cirq.LineQubit.range(2)
    c = _normalized(
        cirq.Circuit(
            (cirq.X**0.5)(q[0]),
            (cirq.X**-0.5)(q[1]),
            cirq.CZ(q[0], q[1]),
            (cirq.Y**0.5)(q[0]),
            (cirq.Y**-0.5)(q[1]),
            cirq.X(q[0]),
            cirq.Z(q[1]),
        )
    )
    u_in = cirq.unitary(c)
    layer_data, _, qubits = extract_layers(c)
    n_boundaries = len(layer_data) + 1
    n = len(qubits)
    internal = (n_boundaries - 1) * n
    assert internal <= 12

    for bits in itertools.product([0, 1], repeat=internal):
        schedule = [{qq: 0 for qq in qubits}]
        idx = 0
        for _ in range(n_boundaries - 1):
            schedule.append({qubits[j]: bits[idx + j] for j in range(n)})
            idx += n
        out = _eject_paulis_through_primitives(apply_schedule(c, schedule))
        assert cirq.equal_up_to_global_phase(
            u_in, cirq.unitary(out)
        ), f"failed for schedule bits {bits}"
