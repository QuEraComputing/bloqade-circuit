import cirq

from bloqade.squin import gate
from bloqade.cirq_utils import load_circuit
from bloqade.squin.passes.parallelize import ParallelizeLayer
from bloqade.squin.layer_optimizer.cost import predicted_layer_count


def _realized(c):
    mt = load_circuit(c)
    ParallelizeLayer(mt.dialects)(mt)
    return sum(
        1
        for s in mt.callable_region.blocks[0].stmts
        if isinstance(s, gate.stmts.Gate)
        and not isinstance(s, (gate.stmts.X, gate.stmts.Y, gate.stmts.Z))
        and not isinstance(s, gate.stmts.ControlledGate)
    )


def _random_brickwork(n_qubits, n_cz_layers, seed):
    import random

    rng = random.Random(seed)
    qs = cirq.LineQubit.range(n_qubits)
    one_q = [
        cirq.X,
        cirq.Y,
        cirq.Z,
        cirq.S,
        cirq.S**-1,
        cirq.X**0.5,
        cirq.X**-0.5,
        cirq.Y**0.5,
        cirq.Y**-0.5,
    ]
    moments = []
    for layer in range(n_cz_layers):
        ops = [rng.choice(one_q)(x) for x in qs if rng.random() < 0.7]
        if ops:
            moments.append(cirq.Moment(ops))
        off = layer % 2
        cz = [cirq.CZ(qs[i], qs[i + 1]) for i in range(off, n_qubits - 1, 2)]
        if cz:
            moments.append(cirq.Moment(cz))
    return cirq.Circuit(moments)


def test_predicted_matches_realized_simple():
    q = cirq.LineQubit.range(2)
    c = cirq.Circuit((cirq.X**0.5)(q[0]), (cirq.X**0.5)(q[1]), cirq.CZ(q[0], q[1]))
    assert predicted_layer_count(c) == _realized(c) == 1


def test_predicted_counts_distinct_types_per_gap():
    q = cirq.LineQubit.range(2)
    c = cirq.Circuit((cirq.X**0.5)(q[0]), (cirq.Y**0.5)(q[1]), cirq.CZ(q[0], q[1]))
    assert predicted_layer_count(c) == _realized(c) == 2


def test_predicted_excludes_paulis():
    q = cirq.LineQubit.range(1)
    c = cirq.Circuit(cirq.X(q[0]), cirq.Z(q[0]))
    assert predicted_layer_count(c) == 0


def test_predicted_within_one_of_realized_on_sweep():
    """The fast cost tracks the realized count closely (off by at most 1).
    Exactness is not required for correctness — the pass materializes through the
    real pipeline with a no-regression guard — but a large drift would mean the
    cost is misguiding the search."""
    from bloqade.cirq_utils import emit_circuit
    from bloqade.squin.passes.clifford_normalize import _normalize

    max_drift = 0
    for seed in range(4):
        c = _random_brickwork(6, 8, seed=seed)
        c_norm = _normalize(emit_circuit(load_circuit(c)))
        max_drift = max(
            max_drift, abs(predicted_layer_count(c_norm) - _realized(c_norm))
        )
    assert max_drift <= 1
