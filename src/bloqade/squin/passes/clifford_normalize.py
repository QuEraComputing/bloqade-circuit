"""CliffordNormalize: convert a Clifford circuit to a canonical form.

Pipeline (cirq-side, round-tripped back to squin):

  1. emit_circuit: squin IR -> cirq.Circuit.
  2. eject Paulis & Z gates to the end (Pauli-frame extraction).
  3. merge consecutive 1q gates into PhasedXZ.
  4. decompose each PhasedXZ into a sequence of quarter-turns around X and Z
     (`{SqrtX, S}` and their inverses, plus Paulis as length-1 matches).
  5. load_circuit: cirq.Circuit -> squin IR; overwrite `mt.code`.
  6. Canonicalize Rx(±π/2) -> SqrtX (via SquinU3ToClifford).

After step 6 the body contains only `{SqrtX±, S±, CZ}`; all `X/Y/Z` Paulis
live in a trailing layer at the very end of the circuit (or are absorbed by
cirq's eject transformers).

This pass does NOT optimize layer counts — it produces a canonical form
that the kirin-native `LayerOptimize` pass then operates on.
"""

from dataclasses import dataclass

import cirq
from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
    ConstantFold,
    CommonSubexpressionElimination,
    abc,
)

from bloqade.cirq_utils import emit_circuit, load_circuit
from bloqade.squin.rewrite import SquinU3ToClifford
from bloqade.squin.layer_optimizer.schedule import _gate_label


# Final gate set: half-turn axis pulses around X and Y, S±, Paulis.
# Including SqrtY± keeps Y-axis rotations as single primitives rather than
# expanding them into a 3-primitive (S · SqrtX · S†) sequence.
def _primitive_ops(q: cirq.Qid) -> list[cirq.Operation]:
    return [
        (cirq.X**0.5)(q),
        (cirq.X**-0.5)(q),
        (cirq.Y**0.5)(q),
        (cirq.Y**-0.5)(q),
        cirq.S(q),
        (cirq.S**-1)(q),
        cirq.X(q),
        cirq.Y(q),
        cirq.Z(q),
    ]


_DECOMP_CACHE: dict[tuple, tuple[cirq.Operation, ...] | None] = {}


def _matrix_key(u) -> tuple:
    """Hashable key for a 2x2 unitary normalized to a canonical global phase."""
    flat = u.reshape(-1)
    pivot = next((x for x in flat if abs(x) > 1e-9), 1.0)
    norm = flat / pivot
    return tuple(round(x.real, 7) + 1j * round(x.imag, 7) for x in norm)


def _decompose_phxz(pxz: cirq.PhasedXZGate, q: cirq.Qid) -> list[cirq.Operation] | None:
    """Find a length<=3 sequence of {SqrtX±, S±, Pauli} matching `pxz`.

    Returns None if the gate is not Clifford-reachable in this primitive set
    (in which case the caller should leave the PhXZ in place).
    """
    target = cirq.unitary(pxz)
    key = _matrix_key(target)
    if key in _DECOMP_CACHE:
        cached = _DECOMP_CACHE[key]
        if cached is None:
            return None
        return [op.gate.on(q) for op in cached]

    if cirq.equal_up_to_global_phase(target, cirq.unitary(cirq.IdentityGate(1))):
        _DECOMP_CACHE[key] = ()
        return []

    primitives = _primitive_ops(q)
    for op in primitives:
        if cirq.equal_up_to_global_phase(target, cirq.unitary(op)):
            _DECOMP_CACHE[key] = (op,)
            return [op]
    for op1 in primitives:
        for op2 in primitives:
            u = cirq.unitary(cirq.Circuit([op1, op2]))
            if cirq.equal_up_to_global_phase(target, u):
                _DECOMP_CACHE[key] = (op1, op2)
                return [op1, op2]
    for op1 in primitives:
        for op2 in primitives:
            for op3 in primitives:
                u = cirq.unitary(cirq.Circuit([op1, op2, op3]))
                if cirq.equal_up_to_global_phase(target, u):
                    _DECOMP_CACHE[key] = (op1, op2, op3)
                    return [op1, op2, op3]
    _DECOMP_CACHE[key] = None
    return None


def _decompose_circuit(circuit: cirq.Circuit) -> cirq.Circuit:
    new_ops = []
    for moment in circuit:
        for op in moment.operations:
            gate = op.gate
            if isinstance(gate, cirq.PhasedXZGate):
                decomp = _decompose_phxz(gate, op.qubits[0])
                if decomp is None:
                    new_ops.append(op)
                else:
                    new_ops.extend(decomp)
            else:
                new_ops.append(op)
    return cirq.Circuit(new_ops)


def _strip_identities(circuit: cirq.Circuit) -> cirq.Circuit:
    """Drop any cirq.I or IdentityGate ops; load_circuit can't lower them."""
    new_moments = []
    for m in circuit:
        ops = [op for op in m.operations if not isinstance(op.gate, cirq.IdentityGate)]
        if ops:
            new_moments.append(cirq.Moment(ops))
    return cirq.Circuit(new_moments)


# Pauli frame propagation through the primitive gate set.
# Conjugation tables (unsigned — we only track Pauli identity, not phase,
# so the daggered primitives share the table of their positive form).
_CONJ_SQRT_X = {"I": "I", "X": "X", "Y": "Z", "Z": "Y"}
_CONJ_SQRT_Y = {"I": "I", "X": "Z", "Y": "Y", "Z": "X"}
_CONJ_S = {"I": "I", "X": "Y", "Y": "X", "Z": "Z"}

_PAULI_MULT = {
    ("I", "I"): "I",
    ("I", "X"): "X",
    ("I", "Y"): "Y",
    ("I", "Z"): "Z",
    ("X", "I"): "X",
    ("X", "X"): "I",
    ("X", "Y"): "Z",
    ("X", "Z"): "Y",
    ("Y", "I"): "Y",
    ("Y", "X"): "Z",
    ("Y", "Y"): "I",
    ("Y", "Z"): "X",
    ("Z", "I"): "Z",
    ("Z", "X"): "Y",
    ("Z", "Y"): "X",
    ("Z", "Z"): "I",
}

_PAULI_GATE = {"X": cirq.X, "Y": cirq.Y, "Z": cirq.Z}


def _eject_paulis_through_primitives(circuit: cirq.Circuit) -> cirq.Circuit:
    """Push body Paulis to a trailing layer AND sign-collapse daggered
    primitives.

    Walks `circuit` (which after decomposition has only {Pauli, SqrtX±, S±,
    SqrtY±, CZ}). For each daggered primitive, emits the positive version
    plus a Pauli into the frame:
      SqrtX† -> SqrtX, frame *= X
      SqrtY† -> SqrtY, frame *= Y
      S†     -> S,     frame *= Z
    Then conjugates the Pauli frame through subsequent Cliffords and
    propagates through CZ. Emits a trailing Pauli layer at the end.
    Result body contains only {SqrtX, SqrtY, S, CZ}.
    """
    qubits = sorted(circuit.all_qubits(), key=lambda q: q.x)
    frame: dict[cirq.Qid, str] = {q: "I" for q in qubits}
    new_ops: list[cirq.Operation] = []

    conj_table = {
        "SqrtX": _CONJ_SQRT_X,
        "SqrtY": _CONJ_SQRT_Y,
        "S": _CONJ_S,
    }
    # When emitting the positive version of a daggered primitive, the
    # discrepancy is this Pauli (left-multiplied into the frame BEFORE
    # the positive op fires).
    sign_compensation = {
        "SqrtXDag": ("SqrtX", "X"),
        "SqrtYDag": ("SqrtY", "Y"),
        "SDag": ("S", "Z"),
    }

    for moment in circuit:
        for op in moment.operations:
            label = _gate_label(op)
            if label in ("X", "Y", "Z"):
                q = op.qubits[0]
                frame[q] = _PAULI_MULT[(frame[q], label)]
            elif label in sign_compensation:
                # Daggered primitive: emit positive form, push the Pauli
                # compensation into the frame (it gets propagated forward
                # by subsequent conjugations).
                q = op.qubits[0]
                pos_label, comp_pauli = sign_compensation[label]
                # frame_new = comp_pauli · (positive op) · frame_old · (positive op)†
                # Since the positive op conjugates the existing frame, do
                # the conjugation first, then multiply by comp_pauli.
                frame[q] = conj_table[pos_label][frame[q]]
                frame[q] = _PAULI_MULT[(comp_pauli, frame[q])]
                pos_gate = {
                    "SqrtX": cirq.X**0.5,
                    "SqrtY": cirq.Y**0.5,
                    "S": cirq.S,
                }[pos_label]
                new_ops.append(pos_gate(q))
            elif label in conj_table:
                q = op.qubits[0]
                frame[q] = conj_table[label][frame[q]]
                new_ops.append(op)
            elif op.gate == cirq.CZ:
                q1, q2 = op.qubits
                p1, p2 = frame[q1], frame[q2]
                # X/Y on one qubit induces Z on the other through CZ.
                new_p1, new_p2 = p1, p2
                if p1 in ("X", "Y"):
                    new_p2 = _PAULI_MULT[(new_p2, "Z")]
                if p2 in ("X", "Y"):
                    new_p1 = _PAULI_MULT[(new_p1, "Z")]
                frame[q1], frame[q2] = new_p1, new_p2
                new_ops.append(op)
            else:
                # Unrecognized — leave it where it is. Conservative: flush
                # the pauli_frame before so the unrecognized op sees the
                # right state.
                for q, p in frame.items():
                    if p != "I":
                        new_ops.append(_PAULI_GATE[p](q))
                        frame[q] = "I"
                new_ops.append(op)

    # Emit the trailing Pauli layer.
    for q in qubits:
        if frame[q] != "I":
            new_ops.append(_PAULI_GATE[frame[q]](q))

    return cirq.Circuit(new_ops)


def _normalize(circuit: cirq.Circuit) -> cirq.Circuit:
    # The eject passes are load-bearing for quality, not just cosmetic:
    # they commute Z-rotations and Paulis toward the end BEFORE the PhXZ
    # merge, which leaves merge_single_qubit_gates_to_phxz with fewer and
    # simpler 1q clusters. Measured on 6q/8-layer random brickwork:
    # removing them costs 2-10 extra 1q-parallel layers after LayerOptimize.
    c = cirq.eject_z(circuit)
    c = cirq.eject_phased_paulis(c)
    c = cirq.eject_z(c)
    c = cirq.merge_single_qubit_gates_to_phxz(c)
    c = _decompose_circuit(c)
    c = _strip_identities(c)
    # Push any Paulis my decomposition emitted (e.g. H -> SqrtY + X)
    # to a single trailing Pauli layer.
    c = _eject_paulis_through_primitives(c)
    return c


def load_normalized(mt: ir.Method, circuit: cirq.Circuit) -> None:
    """Load a normalized cirq circuit back into `mt`, in canonical squin form.

    Shared by CliffordNormalize and LayerOptimize: load_circuit emits
    Rx(±π/2) rather than SqrtX, so canonicalize via SquinU3ToClifford, then
    ConstantFold + CSE collapse each `q[i]` to a single SSA value.
    """
    new_mt = load_circuit(circuit, kernel_name=mt.sym_name, dialects=mt.dialects)
    mt.code = new_mt.code
    Walk(SquinU3ToClifford()).rewrite(mt.code)
    cleanup = Chain(ConstantFold(), CommonSubexpressionElimination())
    Fixpoint(Walk(cleanup)).rewrite(mt.code)


@dataclass
class CliffordNormalize(Pass):
    """Normalize a Clifford circuit to {SqrtX±, S±, CZ} + trailing Paulis."""

    def unsafe_run(self, mt: ir.Method) -> abc.RewriteResult:
        """Normalize ``mt`` in place to the Clifford primitive set."""
        load_normalized(mt, _normalize(emit_circuit(mt)))
        return abc.RewriteResult(has_done_something=True)
