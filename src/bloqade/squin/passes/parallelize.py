from collections import deque
from dataclasses import dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import (
    Walk,
    Chain,
    Fixpoint,
    ConstantFold,
    DeadCodeElimination,
    CommonSubexpressionElimination,
    abc,
)

from bloqade.analysis import address
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.squin.passes import (  # noqa: F401  (registers DagScheduleAnalysis impls for squin.gate)
    _schedule_impls as _schedule_impls,
)
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.squin.analysis import schedule as dag_schedule
from bloqade.squin.rewrite.parallelize import (
    SquinBatchBroadcastsRule,
    merge_key,
    pierce_into_fixed,
)


def _is_diagonal_1q(stmt: ir.Statement) -> bool:
    """True for single-qubit gates that commute with CZ (Z-axis rotations)."""
    return isinstance(stmt, (gate_stmts.S, gate_stmts.Z, gate_stmts.T, gate_stmts.Rz))


@dataclass
class ParallelizeLayer(Pass):
    """Batch single-qubit squin.gate statements into the fewest global pulses,
    treating the 2q (CZ) layers as fixed.

    Pipeline:
      1. AggressiveUnroll inlines `squin.x(q[0])`-style wrappers so gate
         statements appear at the top level for the analysis.
      2. ConstantFold + CSE collapse semantically-identical constants (e.g.
         exponent literals from cirq's `visit_PhasedXZGate`) into shared SSA
         values so the rule's SSA-identity match recognizes equal gates.
      3. Schedule (`_level_partitions`): the CZ layers are pinned at their ASAP
         layer — parallel CZ grouped into one layer, never split or moved — and
         the 1q gates are pierced into the gaps between these fixed walls,
         packing each type into the fewest layers. Diagonal 1q gates (S/S†, Z)
         commute through CZ, so they merge across gaps.
      4. The rule replaces each (layer, type) group's first member with a
         combined broadcast statement and deletes the rest.
      5. ConstantFold + DCE + CSE cleanup removes dead `ilist.New` plumbing.

    SquinToNative lowering downstream emits one global pulse per merged statement
    instead of N separate gates.
    """

    def unsafe_run(self, mt: ir.Method) -> abc.RewriteResult:
        """Run the layer-parallelization pipeline on ``mt`` in place."""
        result = AggressiveUnroll(self.dialects, no_raise=self.no_raise).fixpoint(mt)
        pre_clean = Chain(ConstantFold(), CommonSubexpressionElimination())
        result = Fixpoint(Walk(pre_clean)).rewrite(mt.code).join(result)
        merge_groups, group_numbers = self._build_merge_groups(mt)
        rule = SquinBatchBroadcastsRule(
            merge_groups=merge_groups, group_numbers=group_numbers
        )
        result = Walk(rule).rewrite(mt.code).join(result)
        post_clean = Chain(
            ConstantFold(),
            DeadCodeElimination(),
            CommonSubexpressionElimination(),
        )
        return Fixpoint(Walk(post_clean)).rewrite(mt.code).join(result)

    def _build_merge_groups(
        self, mt: ir.Method
    ) -> tuple[dict[int, list[ir.Statement]], dict[ir.Statement, int]]:
        address_frame, _ = address.AddressAnalysis(mt.dialects).run(mt)
        dags = dag_schedule.DagScheduleAnalysis(
            mt.dialects, address_analysis=address_frame.entries
        ).get_dags(mt)

        merge_groups: dict[int, list[ir.Statement]] = {}
        group_numbers: dict[ir.Statement, int] = {}
        counter = [0]

        def _emit(partitions):
            for members in partitions:
                if len(members) > 1:
                    merge_groups[counter[0]] = members
                    for s in members:
                        group_numbers[s] = counter[0]
                    counter[0] += 1

        for block, dag in dags.items():
            self._level_partitions(block, dag, _emit, address_frame.entries)

        return merge_groups, group_numbers

    @staticmethod
    def _stmt_qubits(stmt: ir.Statement, entries) -> tuple[int, ...] | None:
        """Resolved qubit indices a gate acts on, or None if any are opaque."""
        if isinstance(stmt, gate_stmts.ControlledGate):
            operands = (stmt.controls, stmt.targets)
        else:
            operands = (getattr(stmt, "qubits", None),)
        qubits: list[int] = []
        for ssa in operands:
            if ssa is None:
                return None
            addr = entries.get(ssa)
            if isinstance(addr, address.AddressReg):
                qubits.extend(addr.data)
            elif isinstance(addr, address.AddressQubit):
                qubits.append(addr.data)
            else:
                return None
        return tuple(qubits)

    def _commutation_edges(self, dag, entries):
        """Precedence edges with diagonal 1q gates (S/S†, Z, T, Rz) commuted
        through CZ.

        The data-dependency DAG makes every gate on a qubit serially dependent,
        so it would order an S before a CZ before another qubit's S — but those
        diagonal gates all commute with CZ and could be one pulse. We rebuild the
        per-qubit precedence so a diagonal gate is bounded only by its
        neighbouring non-diagonal gates (√X/√Y/X/Y), never by CZ. Returns
        (inc, out) over all node-ids, or None if a gate's qubits are opaque (then
        the caller keeps the conservative DAG).
        """
        ids = list(dag.stmts.keys())
        qubits_of: dict = {}
        for k in ids:
            qs = self._stmt_qubits(dag.stmts[k], entries)
            if qs is None:
                return None
            qubits_of[k] = qs

        inc: dict = {k: set() for k in ids}
        out: dict = {k: set() for k in ids}

        def link(a, b):
            out[a].add(b)
            inc[b].add(a)

        by_qubit: dict = {}
        for k in sorted(ids, key=lambda k: dag.stmt_index[dag.stmts[k]]):
            for q in qubits_of[k]:
                by_qubit.setdefault(q, []).append(k)

        for chain in by_qubit.values():
            prev_backbone = None  # last non-diagonal gate or CZ
            prev_wall = None  # last non-diagonal 1q gate (√/X/Y)
            prev_diag = None  # last diagonal gate (chained for distinct levels)
            open_diags: list = []  # diagonals awaiting their following wall
            for k in chain:
                if _is_diagonal_1q(dag.stmts[k]):
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
                    if not isinstance(dag.stmts[k], gate_stmts.ControlledGate):
                        for d in open_diags:
                            link(d, k)
                        open_diags = []
                        prev_wall = k
        return inc, out

    @staticmethod
    def _cz_depth(dag, cz_ids, is_cz):
        """ASAP CZ layer of each 2q gate = longest chain of 2q gates ending at
        it (1q gates contracted out). Parallel CZ (no shared qubit) share a
        layer; consecutive layers are ordered — the upstream CZ structure."""

        def cz_succ(start):
            res, stack, seen = set(), list(dag.out_edges[start]), set()
            while stack:
                m = stack.pop()
                if m in seen:
                    continue
                seen.add(m)
                if is_cz[m]:
                    res.add(m)
                else:
                    stack.extend(dag.out_edges[m])
            return res

        out = {k: cz_succ(k) for k in cz_ids}
        inc = {k: set() for k in cz_ids}
        for k in cz_ids:
            for m in out[k]:
                inc[m].add(k)
        indeg = {k: len(inc[k]) for k in cz_ids}
        dq = deque(k for k in cz_ids if indeg[k] == 0)
        depth = {k: 0 for k in cz_ids}
        while dq:
            k = dq.popleft()
            for m in out[k]:
                depth[m] = max(depth[m], depth[k] + 1)
                indeg[m] -= 1
                if indeg[m] == 0:
                    dq.append(m)
        return depth

    def _level_partitions(self, block, dag, emit, entries) -> None:
        ids = list(dag.stmts.keys())
        key_of = {k: merge_key(dag.stmts[k]) for k in ids}
        is_cz = {k: isinstance(dag.stmts[k], gate_stmts.ControlledGate) for k in ids}

        # Work on commutation-aware edges (diagonals commute through CZ) so S
        # gates can merge across CZ gaps; fall back to the raw DAG if qubits are
        # opaque.
        edges = self._commutation_edges(dag, entries)
        inc, out = edges if edges is not None else (dag.inc_edges, dag.out_edges)

        # The 2q (CZ) layers are FIXED at their ASAP layer (the upstream
        # structure): parallel CZ share a layer, consecutive layers are a full
        # BIG-wide slot apart, and they are never moved. The 1q gates are then
        # pierced into the gaps between these immovable walls.
        big = len(ids) + 1
        cz_ids = [k for k in ids if is_cz[k]]
        cz_depth = self._cz_depth(dag, cz_ids, is_cz)
        fixed = {k: (cz_depth[k] + 1) * big for k in cz_ids}
        top = (max(cz_depth.values(), default=-1) + 2) * big

        levels = pierce_into_fixed(ids, inc, out, key_of, fixed, top)
        level = {dag.stmts[k]: levels[k] for k in ids}

        # Reorder this block's gate statements into level order. Safe: gate
        # statements produce no SSA consumed elsewhere, and their qubit-ilist
        # operands (defined earlier, not moved) stay before every use.
        term = block.last_stmt
        for stmt in sorted(
            dag.stmts.values(), key=lambda s: (level[s], dag.stmt_index[s])
        ):
            stmt.detach()
            stmt.insert_before(term)

        # Group by (level, merge_key). Same-level gates are an antichain, hence
        # on disjoint qubits — exactly what SquinBatchBroadcastsRule requires.
        groups: dict[tuple, list[ir.Statement]] = {}
        for k in ids:
            stmt = dag.stmts[k]
            key = key_of[k]
            if key is None:
                continue
            groups.setdefault((level[stmt], key), []).append(stmt)
        for members in groups.values():
            members.sort(key=lambda s: dag.stmt_index[s])
        emit(groups.values())
