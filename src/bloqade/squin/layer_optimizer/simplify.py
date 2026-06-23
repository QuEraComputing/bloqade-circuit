"""Combine per-qubit diagonal (S/S†/Z) runs through CZ into a single gate.

Diagonal gates commute through CZ and are blocked only by that qubit's own axis
gates (√X/√Y/X/Y). Within each segment between consecutive axis gates, all
diagonal quarter-turns combine to a net power of S (mod 4): net 0 -> identity
(dropped), net 2 -> Z (free Pauli), net 1 -> S, net 3 -> S†.
"""

import cirq


def simplify_diagonals(circuit: cirq.Circuit) -> cirq.Circuit:
    """Return an equivalent circuit with per-qubit diagonal runs combined."""
    pending: dict[cirq.Qid, int] = {}
    out: list[cirq.Operation] = []
    s_dag = cirq.S**-1

    def flush(q: cirq.Qid) -> None:
        n = pending.get(q, 0) % 4
        if n == 1:
            out.append(cirq.S(q))
        elif n == 2:
            out.append(cirq.Z(q))
        elif n == 3:
            out.append(s_dag(q))
        pending[q] = 0

    for op in circuit.all_operations():
        g = op.gate
        if g == cirq.CZ:
            out.append(op)
        elif g == cirq.S:
            pending[op.qubits[0]] = pending.get(op.qubits[0], 0) + 1
        elif g == s_dag:
            pending[op.qubits[0]] = pending.get(op.qubits[0], 0) + 3
        elif g == cirq.Z:
            pending[op.qubits[0]] = pending.get(op.qubits[0], 0) + 2
        else:
            flush(op.qubits[0])
            out.append(op)
    for q in list(pending):
        flush(q)
    return cirq.Circuit(out)
