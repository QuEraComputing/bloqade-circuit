"""LayerOptimize: reduce the 1q-parallel layer count of a Clifford circuit.

Pipeline (one cirq round-trip):
  1. emit_circuit + _normalize: squin IR -> canonical cirq circuit.
  2. optimize_threshold_accept: bounded-uphill frame search scored by the fast
     predicted layer count.
  3. Materialize the best frame (apply_schedule + eject + simplify); fall back to
     the unframed circuit if the best frame does not beat it (no-regression
     guard — the only two full-pipeline counts).
  4. load_normalized + ParallelizeLayer.
"""

from dataclasses import dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import abc

from bloqade.squin import gate
from bloqade.cirq_utils import emit_circuit, load_circuit
from bloqade.squin.passes.parallelize import ParallelizeLayer
from bloqade.squin.layer_optimizer.search import optimize_threshold_accept
from bloqade.squin.layer_optimizer.schedule import apply_schedule, extract_layers
from bloqade.squin.layer_optimizer.simplify import simplify_diagonals
from bloqade.squin.passes.clifford_normalize import (
    _normalize,
    load_normalized,
    _eject_paulis_through_primitives,
)

_PAULI = (gate.stmts.X, gate.stmts.Y, gate.stmts.Z)


def _realized_layers(circuit) -> int:
    """Number of 1q pulse layers ParallelizeLayer produces for `circuit`."""
    mt = load_circuit(circuit)
    ParallelizeLayer(mt.dialects)(mt)
    return sum(
        1
        for s in mt.callable_region.blocks[0].stmts
        if isinstance(s, gate.stmts.Gate)
        and not isinstance(s, _PAULI)
        and not isinstance(s, gate.stmts.ControlledGate)
    )


@dataclass
class LayerOptimize(Pass):
    """Reduce 1q-parallel layer count for a Clifford circuit (CZ layers fixed)."""

    def unsafe_run(self, mt: ir.Method) -> abc.RewriteResult:
        """Run the layer optimizer on ``mt`` in place."""
        c_norm = _normalize(emit_circuit(mt))
        layer_data, _, qubits = extract_layers(c_norm)
        chosen = _eject_paulis_through_primitives(c_norm)
        if layer_data:
            sched = optimize_threshold_accept(
                c_norm, layer_data, qubits, _eject_paulis_through_primitives
            )
            best = simplify_diagonals(
                _eject_paulis_through_primitives(apply_schedule(c_norm, sched))
            )
            if _realized_layers(best) < _realized_layers(chosen):
                chosen = best
        load_normalized(mt, chosen)
        return ParallelizeLayer(self.dialects, no_raise=self.no_raise).unsafe_run(mt)
