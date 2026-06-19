import cirq
from kirin import ir

from bloqade import squin
from bloqade.squin import gate
from bloqade.analysis import address
from bloqade.cirq_utils import emit_circuit, load_circuit
from bloqade.squin.passes.parallelize import ParallelizeLayer


def _stmt_count(mt: ir.Method, cls) -> int:
    return sum(1 for s in mt.callable_region.blocks[0].stmts if isinstance(s, cls))


def _n_1q(mt: ir.Method) -> int:
    """Count of 1q (non-CZ) gate statements — the parallel-pulse layer count."""
    return sum(
        1
        for s in mt.callable_region.blocks[0].stmts
        if isinstance(s, gate.stmts.Gate)
        and not isinstance(s, gate.stmts.ControlledGate)
    )


def test_pass_merges_parallel_x_gates_via_dag_analysis():
    @squin.kernel
    def test():
        q = squin.qalloc(3)
        squin.x(q[0])
        squin.x(q[1])
        squin.x(q[2])

    ParallelizeLayer(test.dialects)(test)
    assert _stmt_count(test, gate.stmts.X) == 1, "all three X should collapse into one"
    _, _ = address.AddressAnalysis(test.dialects).run(test)


def test_pass_does_not_merge_across_cz_barrier():
    @squin.kernel
    def test():
        q = squin.qalloc(3)
        squin.x(q[0])
        squin.cz(q[0], q[1])
        # Both q[0] and q[1] now depend on the CZ; second X on q[1] is in a later
        # topological layer than the first X on q[0]. They must not merge.
        squin.x(q[1])

    ParallelizeLayer(test.dialects)(test)
    assert _stmt_count(test, gate.stmts.X) == 2
    assert _stmt_count(test, gate.stmts.CZ) == 1


def test_load_circuit_then_parallelize_collapses_moments():
    q = cirq.LineQubit.range(4)
    circuit = cirq.Circuit(
        cirq.Moment([cirq.X(q[i]) for i in range(4)]),
        cirq.Moment([cirq.S(q[i]) for i in range(4)]),
    )

    mt = load_circuit(circuit)
    assert _stmt_count(mt, gate.stmts.X) == 4
    assert _stmt_count(mt, gate.stmts.S) == 4

    ParallelizeLayer(mt.dialects)(mt)

    assert _stmt_count(mt, gate.stmts.X) == 1
    assert _stmt_count(mt, gate.stmts.S) == 1


def test_load_circuit_phased_xz_moments_merge_after_pass():
    """Replicates the real layer-optimizer use case: cirq emits PhasedXZ per qubit
    with separate py.Constant SSAs; the CSE pre-step inside ParallelizeLayer
    collapses identical exponents so the gates merge."""

    q = cirq.LineQubit.range(3)
    pxz = cirq.PhasedXZGate(x_exponent=0.5, z_exponent=0.25, axis_phase_exponent=0.125)
    circuit = cirq.Circuit(cirq.Moment([pxz.on(qi) for qi in q]))

    mt = load_circuit(circuit)
    assert _stmt_count(mt, gate.stmts.PhasedXZ) == 3

    ParallelizeLayer(mt.dialects)(mt)
    assert _stmt_count(mt, gate.stmts.PhasedXZ) == 1


def test_pass_preserves_address_analysis():
    """After the pass, SSA references must still resolve cleanly."""

    q = cirq.LineQubit.range(4)
    circuit = cirq.Circuit(
        cirq.Moment([cirq.X(q[i]) for i in range(4)]),
        cirq.Moment([cirq.CZ(q[0], q[1]), cirq.CZ(q[2], q[3])]),
        cirq.Moment([cirq.Y(q[i]) for i in range(4)]),
    )
    mt = load_circuit(circuit)
    ParallelizeLayer(mt.dialects)(mt)

    # Sanity: address analysis still resolves cleanly (no broken SSA references).
    _, _ = address.AddressAnalysis(mt.dialects).run(mt)
    # Sanity: each axis pulse collapsed to one statement, CZs collapsed too.
    assert _stmt_count(mt, gate.stmts.X) == 1
    assert _stmt_count(mt, gate.stmts.Y) == 1
    assert _stmt_count(mt, gate.stmts.CZ) == 1


def test_merges_same_type_1q_within_a_gap():
    """Two √X before the same CZ layer (disjoint qubits) merge into one pulse;
    the CZ stays a single statement."""

    @squin.kernel
    def k():
        q = squin.qalloc(2)
        squin.sqrt_x([q[0]])
        squin.sqrt_x([q[1]])
        squin.cz(q[0], q[1])

    ParallelizeLayer(k.dialects)(k)
    assert _stmt_count(k, gate.stmts.SqrtX) == 1
    assert _stmt_count(k, gate.stmts.CZ) == 1


def test_merges_s_across_cz():
    """S commutes through CZ, so two S gates separated only by a CZ merge into
    one pulse."""
    q = cirq.LineQubit.range(2)
    c = cirq.Circuit(
        [
            cirq.S(q[0]),
            cirq.CZ(q[0], q[1]),
            cirq.S(q[1]),
        ]
    )
    u = cirq.unitary(c)

    mt = load_circuit(c)
    ParallelizeLayer(mt.dialects)(mt)

    assert cirq.equal_up_to_global_phase(u, cirq.unitary(emit_circuit(mt)))
    assert _stmt_count(mt, gate.stmts.S) == 1


def test_reduces_1q_layers_over_a_sweep_and_preserves_unitary():
    """Across a brickwork sweep, the pass merges 1q gates (far fewer 1q layers
    than the unmerged input) and preserves the unitary on every circuit."""
    one_q = [cirq.S, cirq.X**0.5, cirq.Y**0.5, cirq.Z, cirq.X]

    for seed in range(5):
        rng = cirq.value.parse_random_state(seed)
        qs = cirq.LineQubit.range(6)
        ops = []
        n_1q_in = 0
        for layer in range(6):
            for x in qs:
                ops.append(one_q[rng.randint(len(one_q))](x))
                n_1q_in += 1
            for i in range(layer % 2, 5, 2):
                ops.append(cirq.CZ(qs[i], qs[i + 1]))
        c = cirq.Circuit(ops)
        u = cirq.unitary(c)

        mt = load_circuit(c)
        ParallelizeLayer(mt.dialects)(mt)
        assert cirq.equal_up_to_global_phase(u, cirq.unitary(emit_circuit(mt)))
        assert _n_1q(mt) < n_1q_in


def _n_1q_counted(mt: ir.Method) -> int:
    """1q (non-CZ) gate statements excluding Paulis — the pulse-layer metric."""
    return sum(
        1
        for s in mt.callable_region.blocks[0].stmts
        if isinstance(s, gate.stmts.Gate)
        and not isinstance(s, gate.stmts.ControlledGate)
        and not isinstance(s, (gate.stmts.X, gate.stmts.Y, gate.stmts.Z))
    )


def test_trailing_paulis_do_not_inflate_layer_count():
    """The ejected Pauli frame is free: appending a trailing Pauli layer must
    not change the counted (non-Pauli) 1q-layer count. Without this the greedy
    scheduler would let trailing Paulis perturb where counted gates land."""
    one_q = [cirq.S, cirq.X**0.5, cirq.Y**0.5]
    for seed in range(6):
        rng = cirq.value.parse_random_state(seed)
        qs = cirq.LineQubit.range(5)
        ops = []
        for layer in range(6):
            for x in qs:
                ops.append(one_q[rng.randint(len(one_q))](x))
            for i in range(layer % 2, 4, 2):
                ops.append(cirq.CZ(qs[i], qs[i + 1]))

        bare = cirq.Circuit(ops)
        with_frame = cirq.Circuit(
            ops + [[cirq.X, cirq.Y, cirq.Z][rng.randint(3)](x) for x in qs]
        )

        mt_bare = load_circuit(bare)
        ParallelizeLayer(mt_bare.dialects)(mt_bare)
        mt_frame = load_circuit(with_frame)
        ParallelizeLayer(mt_frame.dialects)(mt_frame)

        assert _n_1q_counted(mt_frame) == _n_1q_counted(mt_bare), (
            f"seed {seed}: trailing Paulis changed counted layers "
            f"{_n_1q_counted(mt_bare)} -> {_n_1q_counted(mt_frame)}"
        )
        assert cirq.equal_up_to_global_phase(
            cirq.unitary(with_frame), cirq.unitary(emit_circuit(mt_frame))
        )


def test_groups_parallel_cz_into_one_fixed_layer():
    """Parallel (disjoint) CZ are scheduled into one fixed CZ layer — a single
    broadcast statement — rather than fragmented across layers."""

    @squin.kernel
    def k():
        q = squin.qalloc(4)
        squin.cz(q[0], q[1])
        squin.cz(q[2], q[3])  # independent of the first — same fixed layer

    ParallelizeLayer(k.dialects)(k)
    assert _stmt_count(k, gate.stmts.CZ) == 1
