import cirq

from bloqade.squin import gate
from bloqade.cirq_utils import emit_circuit, load_circuit
from bloqade.squin.passes.layer_optimize import LayerOptimize


def _stmt_count(mt, cls):
    return sum(1 for s in mt.callable_region.blocks[0].stmts if isinstance(s, cls))


def test_layer_optimize_preserves_unitary():
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.X(q[0]) ** 0.5,
        cirq.CZ(q[0], q[1]),
        cirq.Y(q[1]) ** 0.5,
    )
    u_before = cirq.unitary(circuit)

    mt = load_circuit(circuit)
    LayerOptimize(mt.dialects)(mt)
    u_after = cirq.unitary(emit_circuit(mt))

    assert cirq.equal_up_to_global_phase(u_before, u_after)


def test_layer_optimize_eliminates_clifford_phased_xz():
    """Clifford PhasedXZ gates get decomposed into {SqrtX, S} primitives;
    non-Clifford PhXZ (e.g., axis_phase=0.25 which is a T-rotation) pass
    through unchanged."""
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.PhasedXZGate(x_exponent=0.5, z_exponent=0.0, axis_phase_exponent=0.0).on(
            q[0]
        ),
        cirq.CZ(q[0], q[1]),
        cirq.PhasedXZGate(x_exponent=0.5, z_exponent=0.5, axis_phase_exponent=0.0).on(
            q[1]
        ),
    )

    mt = load_circuit(circuit)
    LayerOptimize(mt.dialects)(mt)

    assert _stmt_count(mt, gate.stmts.PhasedXZ) == 0


def test_layer_optimize_handles_empty_circuit():
    """A circuit with no 1q gates should still pass without errors."""
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.CZ(q[0], q[1]))

    mt = load_circuit(circuit)
    LayerOptimize(mt.dialects)(mt)
    # CZ should remain
    assert _stmt_count(mt, gate.stmts.CZ) == 1


def test_layer_optimize_preserves_unitary_on_random_circuits():
    """For random small Clifford circuits, LayerOptimize must preserve unitary."""
    import random

    rng = random.Random(42)
    primitives_1q = [
        cirq.X,
        cirq.Y,
        cirq.Z,
        cirq.H,
        cirq.S,
        cirq.S**-1,
        cirq.X**0.5,
        cirq.X**-0.5,
        cirq.Y**0.5,
        cirq.Y**-0.5,
    ]

    for trial in range(20):
        n_qubits = rng.choice([2, 3])
        qs = cirq.LineQubit.range(n_qubits)
        ops = []
        for _ in range(rng.randint(2, 5)):
            for q in qs:
                ops.append(rng.choice(primitives_1q)(q))
            pairs = [(qs[i], qs[i + 1]) for i in range(n_qubits - 1)]
            rng.shuffle(pairs)
            for a, b in pairs[: max(1, n_qubits // 2)]:
                ops.append(cirq.CZ(a, b))
        for q in qs:
            ops.append(rng.choice(primitives_1q)(q))

        c = cirq.Circuit(ops)
        u_in = cirq.unitary(c)
        mt = load_circuit(c)
        LayerOptimize(mt.dialects)(mt)
        u_out = cirq.unitary(emit_circuit(mt))
        assert cirq.equal_up_to_global_phase(
            u_in, u_out
        ), f"trial {trial} failed; circuit:\n{c}"


def _random_brickwork_lo(n_qubits, n_cz_layers, seed, p_1q=0.7):
    import random

    rng = random.Random(seed)
    qs = cirq.LineQubit.range(n_qubits)
    one_q = [
        cirq.X,
        cirq.Y,
        cirq.Z,
        cirq.H,
        cirq.S,
        cirq.S**-1,
        cirq.X**0.5,
        cirq.X**-0.5,
        cirq.Y**0.5,
        cirq.Y**-0.5,
    ]
    moments = []

    def add_1q():
        ops = [rng.choice(one_q)(q) for q in qs if rng.random() < p_1q]
        if ops:
            moments.append(cirq.Moment(ops))

    for layer in range(n_cz_layers):
        add_1q()
        off = layer % 2
        cz = [cirq.CZ(qs[i], qs[i + 1]) for i in range(off, n_qubits - 1, 2)]
        if cz:
            moments.append(cirq.Moment(cz))
    add_1q()
    return cirq.Circuit(moments)


def _n_1q(mt):
    return sum(
        1
        for s in mt.callable_region.blocks[0].stmts
        if isinstance(s, gate.stmts.Gate)
        and not isinstance(s, (gate.stmts.X, gate.stmts.Y, gate.stmts.Z))
        and not isinstance(s, gate.stmts.ControlledGate)
    )


def test_layer_optimize_seed0_reaches_six():
    c = _random_brickwork_lo(6, 8, seed=0)
    u = cirq.unitary(c)
    mt = load_circuit(c)
    LayerOptimize(mt.dialects)(mt)
    assert cirq.equal_up_to_global_phase(u, cirq.unitary(emit_circuit(mt)))
    assert _n_1q(mt) <= 6


def test_layer_optimize_no_regression_sweep():
    for seed in range(4):
        c = _random_brickwork_lo(6, 8, seed=seed)
        u = cirq.unitary(c)
        mt = load_circuit(c)
        LayerOptimize(mt.dialects)(mt)
        assert cirq.equal_up_to_global_phase(u, cirq.unitary(emit_circuit(mt)))


def test_layer_optimize_beats_or_matches_unframed_baseline():
    """On a seed sweep, LayerOptimize never produces more 1q layers than the
    unframed normalized baseline, and improves on average."""
    from bloqade.squin.passes.layer_optimize import _realized_layers
    from bloqade.squin.passes.clifford_normalize import (
        _normalize,
        _eject_paulis_through_primitives,
    )

    total_base = 0
    total_opt = 0
    for seed in range(4):
        c = _random_brickwork_lo(6, 8, seed=seed)
        c_norm = _normalize(emit_circuit(load_circuit(c)))
        base = _realized_layers(_eject_paulis_through_primitives(c_norm))

        mt_opt = load_circuit(c)
        LayerOptimize(mt_opt.dialects)(mt_opt)
        opt = _n_1q(mt_opt)

        assert opt <= base, f"seed {seed}: regression {opt} > {base}"
        total_base += base
        total_opt += opt

    assert total_opt < total_base


def test_layer_optimize_preserves_unitary_multilayer():
    """LayerOptimize preserves the unitary on a multi-layer circuit with merge
    opportunities."""
    q = cirq.LineQubit.range(3)
    c = cirq.Circuit(
        [
            (cirq.X**0.5)(q[2]),
            cirq.CZ(q[0], q[1]),
            (cirq.X**0.5)(q[0]),
            cirq.CZ(q[1], q[2]),
            (cirq.Y**0.5)(q[0]),
        ]
    )
    u = cirq.unitary(c)
    mt = load_circuit(c)
    LayerOptimize(mt.dialects)(mt)
    assert cirq.equal_up_to_global_phase(u, cirq.unitary(emit_circuit(mt)))


def test_layer_optimize_keeps_paulis_trailing():
    """simplify_diagonals can emit a fresh Z when a diagonal run nets to 2 mod 4;
    the pass must eject it so all Paulis stay in the trailing layer (no Pauli
    followed by a non-Pauli on the same qubit)."""
    q = cirq.LineQubit.range(3)
    # S,S on q0 nets to Z; the CZ then an axis gate force a mid-circuit flush
    # inside simplify_diagonals.
    c = cirq.Circuit(
        [
            cirq.S(q[0]),
            cirq.S(q[0]),
            cirq.CZ(q[0], q[1]),
            (cirq.X**0.5)(q[0]),
            cirq.CZ(q[1], q[2]),
            (cirq.Y**0.5)(q[1]),
        ]
    )
    u = cirq.unitary(c)
    mt = load_circuit(c)
    LayerOptimize(mt.dialects)(mt)
    out = emit_circuit(mt)
    assert cirq.equal_up_to_global_phase(u, cirq.unitary(out))

    pauli = (cirq.X, cirq.Y, cirq.Z)
    for qb in out.all_qubits():
        seen_pauli = False
        for moment in out:
            op = moment.operation_at(qb)
            if op is None:
                continue
            is_pauli = op.gate in pauli
            assert not (
                seen_pauli and not is_pauli
            ), f"non-Pauli after Pauli on {qb} in:\n{out}"
            seen_pauli = seen_pauli or is_pauli
