"""Cirq op-space layer scheduling.

Two halves of the layer optimizer that touch the circuit representation:

  - extract_layers: read the per-CZ-gap structure (intrinsic axis per qubit,
    S-residue qubits) that the cirq-free greedy search consumes.
  - apply_schedule: materialize the greedy's chosen frame schedule by
    S-conjugation.

Both operate on a cirq.Circuit already in CliffordNormalize form
(body = {SqrtX, SqrtY, S, CZ}, Paulis trailing).

Materialization inserts ONE S where a qubit's frame turns on (0->1) and one
S† where it turns off (1->0), conjugating every gate inside an active frame:

    SqrtX <-> SqrtY,   X <-> Y,   S and Z unchanged.

Because S commutes through CZ, a frame persists across walls untouched, and
the inserted S / S† telescope — so the result equals the input up to the
trailing Pauli layer, with no per-qubit bookkeeping. Daggers and Paulis that
conjugation introduces are cleaned up by re-running the Pauli ejector.
"""

import cirq


def _gate_label(op: cirq.Operation) -> str | None:
    g = op.gate
    if g == cirq.X:
        return "X"
    if g == cirq.Y:
        return "Y"
    if g == cirq.Z:
        return "Z"
    if g == cirq.S:
        return "S"
    if g == cirq.S**-1:
        return "SDag"
    if g == cirq.X**0.5:
        return "SqrtX"
    if g == cirq.X**-0.5:
        return "SqrtXDag"
    if g == cirq.Y**0.5:
        return "SqrtY"
    if g == cirq.Y**-0.5:
        return "SqrtYDag"
    return None


_AXIS = {"SqrtX": "X", "SqrtY": "Y"}


def extract_layers(
    circuit: cirq.Circuit,
) -> tuple[list[dict], list[set], list[cirq.Qid]]:
    """Return (layer_data, s_qubits, qubits) partitioned by CZ wall.

    All lists are indexed by gap (gap 0 before the first CZ). `layer_data[i]`
    maps qubit -> intrinsic axis ('X' or 'Y'); `s_qubits[i]` is the set of
    qubits with an S residue in gap i; `qubits` is every qubit, first-seen.
    """
    layer_data: list[dict] = [{}]
    s_qubits: list[set] = [set()]
    qubits: list[cirq.Qid] = []
    seen: set = set()

    def _rec(q):
        if q not in seen:
            seen.add(q)
            qubits.append(q)

    for op in circuit.all_operations():
        if op.gate == cirq.CZ:
            for q in op.qubits:
                _rec(q)
            layer_data.append({})
            s_qubits.append(set())
            continue
        q = op.qubits[0]
        _rec(q)
        label = _gate_label(op)
        if label in _AXIS:
            layer_data[-1][q] = _AXIS[label]
        elif label in ("S", "SDag"):
            s_qubits[-1].add(q)
    return layer_data, s_qubits, qubits


# Conjugation of a body gate by S^1 (S g S†), keyed by _gate_label.
_CONJ = {
    "SqrtX": lambda q: (cirq.Y**0.5)(q),
    "SqrtY": lambda q: (cirq.X**-0.5)(q),
    "S": lambda q: cirq.S(q),
    "SDag": lambda q: (cirq.S**-1)(q),
    "X": lambda q: cirq.Y(q),
    "Y": lambda q: cirq.X(q),
    "Z": lambda q: cirq.Z(q),
}


def apply_schedule(circuit: cirq.Circuit, schedule: list[dict]) -> cirq.Circuit:
    """Rewrite `circuit` to realize `schedule` (length num_gaps + 1).

    `schedule[i]` is the per-qubit frame (0/1) in effect during gap i-1 ->
    gap i; schedule[0] is the all-zero initial frame. Returns a new circuit;
    the caller should re-run the Pauli ejector to collapse the daggers and
    Paulis this introduces.
    """
    gaps: list[list[cirq.Operation]] = [[]]
    walls: list[cirq.Operation] = []
    for op in circuit.all_operations():
        if op.gate == cirq.CZ:
            walls.append(op)
            gaps.append([])
        else:
            gaps[-1].append(op)

    if len(schedule) != len(gaps) + 1:
        raise ValueError(
            f"schedule length {len(schedule)} != num_gaps+1 {len(gaps) + 1}"
        )

    new_ops: list[cirq.Operation] = []
    frame: dict = {}
    for i, gap in enumerate(gaps):
        for q, target in schedule[i + 1].items():
            cur = frame.get(q, 0)
            if target > cur:
                new_ops.append(cirq.S(q))
            elif target < cur:
                new_ops.append((cirq.S**-1)(q))
            frame[q] = target
        for op in gap:
            q = op.qubits[0]
            if frame.get(q, 0) % 2:
                conj = _CONJ.get(_gate_label(op))
                if conj is None:
                    raise ValueError(
                        f"cannot conjugate non-normalized gate {op.gate!r}; "
                        "expected CliffordNormalize form {SqrtX, SqrtY, S, "
                        "X, Y, Z, CZ}"
                    )
                new_ops.append(conj(q))
            else:
                new_ops.append(op)
        if i < len(walls):
            new_ops.append(walls[i])

    # Close any still-active frame so the lab frame returns to identity.
    for q, f in frame.items():
        if f % 2:
            new_ops.append((cirq.S**-1)(q))

    return cirq.Circuit(new_ops)
