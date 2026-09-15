"""Fast 1q pulse-layer count for a normalized cirq circuit.

`predicted_layer_count` reuses ParallelizeLayer's scheduler (`pierce_into_fixed`)
on a cheap graph built directly from a cirq circuit — no IR — so the frame search
can score candidates cheaply. The count is the number of distinct (level,
gate-type) groups among non-Pauli 1q gates, matching what ParallelizeLayer
materializes.
"""

from collections import deque

import cirq

from bloqade.squin.rewrite.parallelize import pierce_into_fixed

_CZ = cirq.CZ
_DIAG = frozenset({cirq.S, cirq.S**-1, cirq.Z})
_PAULI = frozenset({cirq.X, cirq.Y, cirq.Z})


def predicted_layer_count(circuit: cirq.Circuit) -> int:
    """Predicted number of 1q pulse layers ParallelizeLayer would produce."""
    ops = list(circuit.all_operations())
    ids = list(range(len(ops)))
    gate = [op.gate for op in ops]
    is_cz = [g == _CZ for g in gate]
    is_diag = [g in _DIAG for g in gate]

    by_qubit: dict = {}
    for i in ids:
        for q in ops[i].qubits:
            by_qubit.setdefault(q, []).append(i)

    raw_out = {i: set() for i in ids}
    for chain in by_qubit.values():
        for a, b in zip(chain, chain[1:]):
            raw_out[a].add(b)

    inc = {i: set() for i in ids}
    out = {i: set() for i in ids}

    def link(a, b):
        out[a].add(b)
        inc[b].add(a)

    # Commutation edges: diagonals bounded by neighbouring non-diagonal gates,
    # never by CZ (mirrors ParallelizeLayer._commutation_edges).
    for chain in by_qubit.values():
        prev_backbone = prev_wall = prev_diag = None
        open_diags: list = []
        for k in chain:
            if is_diag[k]:
                if prev_wall is not None:
                    link(prev_wall, k)
                if prev_diag is not None:
                    link(prev_diag, k)
                prev_diag = k
                open_diags.append(k)
            else:
                if prev_backbone is not None:
                    link(prev_backbone, k)
                prev_backbone = k
                if not is_cz[k]:
                    for d in open_diags:
                        link(d, k)
                    open_diags = []
                    prev_wall = k

    cz_ids = [i for i in ids if is_cz[i]]

    def cz_succ(start):
        res, stack, seen = set(), list(raw_out[start]), set()
        while stack:
            m = stack.pop()
            if m in seen:
                continue
            seen.add(m)
            if is_cz[m]:
                res.add(m)
            else:
                stack.extend(raw_out[m])
        return res

    succ = {k: cz_succ(k) for k in cz_ids}
    cinc = {k: set() for k in cz_ids}
    for k in cz_ids:
        for m in succ[k]:
            cinc[m].add(k)
    indeg = {k: len(cinc[k]) for k in cz_ids}
    dq = deque(k for k in cz_ids if indeg[k] == 0)
    depth = {k: 0 for k in cz_ids}
    while dq:
        k = dq.popleft()
        for m in succ[k]:
            depth[m] = max(depth[m], depth[k] + 1)
            indeg[m] -= 1
            if indeg[m] == 0:
                dq.append(m)

    big = len(ids) + 1
    fixed = {k: (depth[k] + 1) * big for k in cz_ids}
    top = (max(depth.values(), default=-1) + 2) * big
    key_of = {i: gate[i] for i in ids}
    levels = pierce_into_fixed(ids, inc, out, key_of, fixed, top)

    groups = set()
    for i in ids:
        if is_cz[i] or gate[i] in _PAULI:
            continue
        groups.add((levels[i], gate[i]))
    return len(groups)
