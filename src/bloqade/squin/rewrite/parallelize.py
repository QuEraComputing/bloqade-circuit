from collections import deque
from dataclasses import field, dataclass

from kirin import ir
from kirin.dialects import ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin.gate import stmts as gate_stmts


def merge_key(stmt: ir.Statement) -> tuple | None:
    """Return a hashable key identifying which broadcast partition a statement belongs to.

    Returns None when the statement cannot be batched (unsupported type).
    """
    if isinstance(stmt, gate_stmts.SingleQubitNonHermitianGate):
        return (type(stmt), stmt.adjoint)
    if isinstance(stmt, gate_stmts.SingleQubitGate):
        return (type(stmt),)
    if isinstance(stmt, gate_stmts.RotationGate):
        return (type(stmt), stmt.angle)
    if isinstance(stmt, gate_stmts.ControlledGate):
        return (type(stmt),)
    if isinstance(stmt, gate_stmts.PhasedXZ):
        return (
            type(stmt),
            stmt.x_exponent,
            stmt.z_exponent,
            stmt.axis_phase_exponent,
        )
    return None


def pierce_into_fixed(
    node_ids: list,
    inc_edges: dict,
    out_edges: dict,
    key_of: dict,
    fixed_levels: dict,
    top: int,
) -> dict:
    """Place the free nodes at levels minimizing distinct (level, key) groups,
    with the fixed nodes (e.g. CZ layers) held at given immovable levels.

    Backward delay-to-merge: process nodes successors-first; place each free node
    at the latest level in its window that already hosts its key — joining that
    group — else at the latest feasible level. A free node's window is its
    forward lower bound (from fixed/free predecessors) up to the min of its
    already-placed successors (fixed walls and placed free nodes). Respects
    precedence (level[pred] < level[succ]), so e.g. a √X never crosses a CZ on
    its qubit while an S (whose CZ edges are dropped upstream) freely does.

    Operates on plain adjacency so it is testable without IR.
      node_ids: all node ids (free + fixed)
      inc_edges/out_edges: id -> set of predecessor/successor ids
      key_of: id -> merge_key (None = placed but never merged)
      fixed_levels: id -> level for the immovable nodes
      top: a level strictly above every fixed level (window cap for sinks)
    Returns: id -> level for ALL nodes.
    """
    indeg = {n: len(inc_edges[n]) for n in node_ids}
    dq = deque(n for n in node_ids if indeg[n] == 0)
    order: list = []
    while dq:
        n = dq.popleft()
        order.append(n)
        for m in out_edges[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                dq.append(m)

    placed = dict(fixed_levels)
    # Forward lower bound for each free node (respects fixed walls + free chains).
    lo: dict = {}
    for n in order:
        if n in fixed_levels:
            continue
        lo[n] = max(
            (placed[p] + 1 if p in fixed_levels else lo[p] + 1 for p in inc_edges[n]),
            default=0,
        )

    used: dict = {}  # key -> set of used levels
    for n in reversed(order):
        if n in fixed_levels:
            continue
        k = key_of[n]
        hi = max(min((placed[s] - 1 for s in out_edges[n]), default=top), lo[n])
        level = None
        if k is not None:
            cands = [s for s in used.get(k, ()) if lo[n] <= s <= hi]
            if cands:
                level = max(cands)
        if level is None:
            level = hi
        placed[n] = level
        if k is not None:
            used.setdefault(k, set()).add(level)

    for n in node_ids:
        for m in out_edges[n]:
            if placed[n] >= placed[m]:
                raise RuntimeError("pierce_into_fixed: precedence violated")
    return placed


def _ilist_values(ssa: ir.SSAValue) -> tuple[ir.SSAValue, ...] | None:
    """Return the values of an ilist.New that produced this SSA value, or None if opaque."""
    if isinstance(ssa, ir.ResultValue) and isinstance(ssa.stmt, ilist.New):
        return tuple(ssa.stmt.values)
    return None


@dataclass
class SquinBatchBroadcastsRule(RewriteRule):
    """Merge same-type squin.gate statements on disjoint qubits into one broadcast.

    Statements are batched according to a precomputed assignment:
      - `merge_groups[g]` is the ordered list of statements in group `g`.
      - `group_numbers[stmt]` is the group id for a statement (absent → not batched).

    When the rule sees the first statement of a group it constructs a single replacement
    statement whose `qubits` ilist concatenates each group member's qubits. Subsequent
    statements in the same group are deleted.

    The caller (typically `ParallelizeLayer`) is responsible for ensuring statements in
    the same group operate on disjoint qubits. The rule raises ``ValueError`` if this
    invariant is violated when combining qubit lists.
    """

    merge_groups: dict[int, list[ir.Statement]]
    group_numbers: dict[ir.Statement, int]
    group_has_merged: dict[int, bool] = field(default_factory=dict)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Merge ``node`` into its broadcast group, or delete it if absorbed."""
        group_id = self.group_numbers.get(node)
        if group_id is None:
            return RewriteResult()
        group = self.merge_groups[group_id]
        if node is group[0]:
            ok = self._merge_first(node, group)
            self.group_has_merged[group_id] = ok
            return RewriteResult(has_done_something=ok)
        if self.group_has_merged.get(group_id, False):
            node.delete()
            return RewriteResult(has_done_something=True)
        return RewriteResult()

    def _merge_first(self, node: ir.Statement, group: list[ir.Statement]) -> bool:
        """Build the combined broadcast statement and insert it before `node`."""
        if isinstance(node, gate_stmts.ControlledGate):
            return self._merge_controlled(node, group)
        combined_qubits = self._combine_qubits([s.qubits for s in group])
        if combined_qubits is None:
            return False
        new_ilist = ilist.New(values=combined_qubits)
        new_ilist.insert_before(node)
        new_stmt = self._build_merged(node, new_ilist.result)
        node.replace_by(new_stmt)
        return True

    def _merge_controlled(self, node: ir.Statement, group: list[ir.Statement]) -> bool:
        combined_ctrls = self._combine_qubits([s.controls for s in group])
        combined_tgts = self._combine_qubits([s.targets for s in group])
        if combined_ctrls is None or combined_tgts is None:
            return False
        new_ctrls = ilist.New(values=combined_ctrls)
        new_tgts = ilist.New(values=combined_tgts)
        new_ctrls.insert_before(node)
        new_tgts.insert_before(node)
        new_stmt = type(node)(controls=new_ctrls.result, targets=new_tgts.result)
        node.replace_by(new_stmt)
        return True

    def _build_merged(
        self, node: ir.Statement, qubits_ssa: ir.SSAValue
    ) -> ir.Statement:
        """Construct a replacement statement of the same type as `node` with combined qubits."""
        cls = type(node)
        if isinstance(node, gate_stmts.SingleQubitNonHermitianGate):
            return cls(adjoint=node.adjoint, qubits=qubits_ssa)
        if isinstance(node, gate_stmts.RotationGate):
            return cls(angle=node.angle, qubits=qubits_ssa)
        if isinstance(node, gate_stmts.PhasedXZ):
            return cls(
                x_exponent=node.x_exponent,
                z_exponent=node.z_exponent,
                axis_phase_exponent=node.axis_phase_exponent,
                qubits=qubits_ssa,
            )
        return cls(qubits=qubits_ssa)

    def _combine_qubits(
        self, qubit_ssas: list[ir.SSAValue]
    ) -> tuple[ir.SSAValue, ...] | None:
        """Concatenate the qubit ilists of each statement, or None if any is opaque.

        Asserts the result has no duplicates — the caller must guarantee the input
        statements operate on disjoint qubits.
        """
        combined: list[ir.SSAValue] = []
        for ssa in qubit_ssas:
            values = _ilist_values(ssa)
            if values is None:
                return None
            combined.extend(values)
        if len(combined) != len(set(combined)):
            raise ValueError("merge groups must contain statements on disjoint qubits")
        return tuple(combined)
