import cirq

from bloqade.cirq_utils import emit_circuit, load_circuit
from bloqade.squin.layer_optimizer.cost import predicted_layer_count
from bloqade.squin.layer_optimizer.search import optimize_threshold_accept
from bloqade.squin.layer_optimizer.schedule import apply_schedule, extract_layers
from bloqade.squin.layer_optimizer.simplify import simplify_diagonals
from bloqade.squin.passes.clifford_normalize import (
    _normalize,
    _eject_paulis_through_primitives,
)


def _random_brickwork(n_qubits, n_cz_layers, seed, p_1q=0.7):
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


def _materialize(c_norm, sched):
    return simplify_diagonals(
        _eject_paulis_through_primitives(apply_schedule(c_norm, sched))
    )


def test_search_reaches_six_on_seed0_fast():
    c = _random_brickwork(6, 8, seed=0)
    c_norm = _normalize(emit_circuit(load_circuit(c)))
    layer_data, _, qubits = extract_layers(c_norm)
    sched = optimize_threshold_accept(
        c_norm, layer_data, qubits, _eject_paulis_through_primitives
    )
    assert predicted_layer_count(_materialize(c_norm, sched)) <= 6


def test_search_never_worse_than_zero_frame():
    c = _random_brickwork(6, 8, seed=2)
    c_norm = _normalize(emit_circuit(load_circuit(c)))
    layer_data, _, qubits = extract_layers(c_norm)
    zero = [{q: 0 for q in qubits}] + [
        {q: 0 for q in qubits} for _ in range(len(layer_data))
    ]
    sched = optimize_threshold_accept(
        c_norm, layer_data, qubits, _eject_paulis_through_primitives
    )
    assert predicted_layer_count(_materialize(c_norm, sched)) <= predicted_layer_count(
        _materialize(c_norm, zero)
    )
