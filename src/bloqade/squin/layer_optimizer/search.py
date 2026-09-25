"""Bounded-uphill frame search for LayerOptimize.

Plateau moves are inert for this problem (every single frame flip is strictly
uphill), so acceptance allows a bounded uphill step (tau=1) and keeps the best
frame seen. Deterministic (fixed move order + tabu, no RNG). The objective is
the fast `predicted_layer_count` of the materialized frame.

The `eject` callable (a cirq.Circuit -> cirq.Circuit Pauli ejector) is passed in
by the caller so this module stays a leaf — it must run before counting, because
conjugation in apply_schedule produces daggered gates (e.g. √Y -> √X†) that
eject collapses to the positive gate + a free Pauli; counting them undaggered
would inflate the distinct-type tally.
"""

from bloqade.squin.layer_optimizer.cost import predicted_layer_count
from bloqade.squin.layer_optimizer.schedule import apply_schedule
from bloqade.squin.layer_optimizer.simplify import simplify_diagonals


def _key(frame: dict, qubits) -> tuple:
    return tuple(tuple(frame[q]) for q in qubits)


def _schedule(frame: dict, qubits, n_gaps: int) -> list:
    return [{q: 0 for q in qubits}] + [
        {q: frame[q][i] for q in qubits} for i in range(n_gaps)
    ]


def optimize_threshold_accept(
    c_norm, layer_data, qubits, eject, *, tau: int = 1, max_iters: int = 200
) -> list:
    """Deterministic bounded-uphill search; returns the best frame schedule.

    `eject` is a cirq.Circuit -> cirq.Circuit Pauli ejector applied before each
    cost evaluation.
    """
    n_gaps = len(layer_data)
    moves = [(q, i) for i in range(n_gaps) for q in layer_data[i]]
    frame = {q: [0] * n_gaps for q in qubits}

    def cost(sched):
        return predicted_layer_count(
            simplify_diagonals(eject(apply_schedule(c_norm, sched)))
        )

    cur = cost(_schedule(frame, qubits, n_gaps))
    best, best_frame = cur, {q: frame[q][:] for q in qubits}
    seen = {_key(frame, qubits)}
    for _ in range(max_iters):
        chosen = chosen_cost = chosen_key = None
        for q, i in moves:
            frame[q][i] ^= 1
            k = _key(frame, qubits)
            c = cost(_schedule(frame, qubits, n_gaps)) if k not in seen else None
            frame[q][i] ^= 1
            if (
                c is not None
                and c - cur <= tau
                and (chosen_cost is None or c < chosen_cost)
            ):
                chosen, chosen_cost, chosen_key = (q, i), c, k
        if chosen is None:
            break
        frame[chosen[0]][chosen[1]] ^= 1
        seen.add(chosen_key)
        cur = chosen_cost
        if cur < best:
            best, best_frame = cur, {q: frame[q][:] for q in qubits}
    return _schedule(best_frame, qubits, n_gaps)
