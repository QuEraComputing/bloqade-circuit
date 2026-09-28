from kirin import ir
from kirin.rewrite import Walk
from kirin.dialects import ilist

from bloqade import squin
from bloqade.squin import gate
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.squin.rewrite.parallelize import (
    SquinBatchBroadcastsRule,
    merge_key,
    pierce_into_fixed,
)


def _gate_stmts(mt: ir.Method, cls) -> list[ir.Statement]:
    return [s for s in mt.callable_region.blocks[0].stmts if isinstance(s, cls)]


def _build_rule_simple(mt: ir.Method) -> SquinBatchBroadcastsRule:
    """Test helper: group every same-type gate stmt into one merge group.

    Caller must ensure the input kernel has only disjoint-qubit gates of each type
    (the rule itself asserts disjointness when it merges).
    """
    by_type: dict[type, list[ir.Statement]] = {}
    for s in mt.callable_region.blocks[0].stmts:
        if isinstance(s, gate.stmts.Gate):
            by_type.setdefault(type(s), []).append(s)
    merge_groups: dict[int, list[ir.Statement]] = {}
    group_numbers: dict[ir.Statement, int] = {}
    for i, group in enumerate(by_type.values()):
        if len(group) > 1:
            merge_groups[i] = group
            for s in group:
                group_numbers[s] = i
    return SquinBatchBroadcastsRule(
        merge_groups=merge_groups, group_numbers=group_numbers
    )


def test_smoke_kernel_lowers_to_gate_stmts_after_unroll():
    """Confirms: `squin.x(q[0])` + AggressiveUnroll produces gate.stmts.X at the top level."""

    @squin.kernel
    def test():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.x(q[1])

    AggressiveUnroll(test.dialects).fixpoint(test)

    xs = _gate_stmts(test, gate.stmts.X)
    assert len(xs) == 2, "expected two X stmts at the top level after inlining"
    # Each X holds a single-qubit ilist
    for x in xs:
        assert isinstance(x.qubits.owner, ilist.New)
        assert len(x.qubits.owner.values) == 1


def test_two_x_on_disjoint_qubits_merge():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.x(q[1])

    AggressiveUnroll(test.dialects).fixpoint(test)
    rule = _build_rule_simple(test)
    Walk(rule).rewrite(test.code)

    xs = _gate_stmts(test, gate.stmts.X)
    assert len(xs) == 1, "two X stmts should collapse to one"
    qubits_stmt = xs[0].qubits.owner
    assert isinstance(qubits_stmt, ilist.New)
    assert len(qubits_stmt.values) == 2


def test_y_z_h_all_merge_similarly():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        squin.y(q[0])
        squin.y(q[1])
        squin.z(q[0])
        squin.z(q[1])
        squin.h(q[0])
        squin.h(q[1])

    AggressiveUnroll(test.dialects).fixpoint(test)
    rule = _build_rule_simple(test)
    Walk(rule).rewrite(test.code)

    assert len(_gate_stmts(test, gate.stmts.Y)) == 1
    assert len(_gate_stmts(test, gate.stmts.Z)) == 1
    assert len(_gate_stmts(test, gate.stmts.H)) == 1


def test_different_types_do_not_merge():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.y(q[1])

    AggressiveUnroll(test.dialects).fixpoint(test)
    rule = _build_rule_simple(test)
    Walk(rule).rewrite(test.code)

    # Different types live in different groups (none with size > 1), so no merging.
    assert len(_gate_stmts(test, gate.stmts.X)) == 1
    assert len(_gate_stmts(test, gate.stmts.Y)) == 1


def _build_rule_keyed(
    mt: ir.Method, attr_names_by_type: dict[type, tuple[str, ...]]
) -> SquinBatchBroadcastsRule:
    """Test helper: group stmts by (type, *attr_values) — for non-Hermitian and parameterized gates."""
    groups: dict[tuple, list[ir.Statement]] = {}
    for s in mt.callable_region.blocks[0].stmts:
        if not isinstance(s, gate.stmts.Gate):
            continue
        attr_names = attr_names_by_type.get(type(s), ())
        key = (type(s),) + tuple(getattr(s, n) for n in attr_names)
        groups.setdefault(key, []).append(s)
    merge_groups: dict[int, list[ir.Statement]] = {}
    group_numbers: dict[ir.Statement, int] = {}
    for i, group in enumerate(groups.values()):
        if len(group) > 1:
            merge_groups[i] = group
            for s in group:
                group_numbers[s] = i
    return SquinBatchBroadcastsRule(
        merge_groups=merge_groups, group_numbers=group_numbers
    )


def test_same_adjoint_s_gates_merge():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        squin.s(q[0])
        squin.s(q[1])

    AggressiveUnroll(test.dialects).fixpoint(test)
    rule = _build_rule_keyed(test, attr_names_by_type={gate.stmts.S: ("adjoint",)})
    Walk(rule).rewrite(test.code)
    ss = _gate_stmts(test, gate.stmts.S)
    assert len(ss) == 1
    assert ss[0].adjoint is False


def test_different_adjoint_s_gates_do_not_merge():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        squin.s(q[0])
        squin.s_adj(q[1])

    AggressiveUnroll(test.dialects).fixpoint(test)
    rule = _build_rule_keyed(test, attr_names_by_type={gate.stmts.S: ("adjoint",)})
    Walk(rule).rewrite(test.code)
    ss = _gate_stmts(test, gate.stmts.S)
    assert len(ss) == 2, "S(False) and S(True) must not merge"


def test_merge_key_distinguishes_adjoint():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        squin.s(q[0])
        squin.s_adj(q[1])

    AggressiveUnroll(test.dialects).fixpoint(test)
    s_stmts = _gate_stmts(test, gate.stmts.S)
    assert len(s_stmts) == 2
    assert merge_key(s_stmts[0]) != merge_key(s_stmts[1])
    keys = {merge_key(s) for s in s_stmts}
    assert (gate.stmts.S, False) in keys
    assert (gate.stmts.S, True) in keys


def test_merge_key_unsupported_returns_none():
    @squin.kernel
    def test():
        squin.qalloc(1)

    AggressiveUnroll(test.dialects).fixpoint(test)
    for s in test.callable_region.blocks[0].stmts:
        if not isinstance(s, gate.stmts.Gate):
            assert merge_key(s) is None


def test_rotation_with_same_angle_ssa_merges():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        angle = 0.25
        squin.rx(angle, q[0])
        squin.rx(angle, q[1])

    AggressiveUnroll(test.dialects).fixpoint(test)
    rule = _build_rule_keyed(test, attr_names_by_type={gate.stmts.Rx: ("angle",)})
    Walk(rule).rewrite(test.code)
    rxs = _gate_stmts(test, gate.stmts.Rx)
    assert len(rxs) == 1
    qubits_stmt = rxs[0].qubits.owner
    assert isinstance(qubits_stmt, ilist.New)
    assert len(qubits_stmt.values) == 2


def test_rotation_with_distinct_angle_values_does_not_merge():
    """Different angle values produce distinct SSA values → distinct keys → no merge.

    Note: identical literal values get deduplicated by CSE inside AggressiveUnroll,
    so distinct-but-equal-literal angles WOULD merge. Use truly different values to
    exercise the negative path."""

    @squin.kernel
    def test():
        q = squin.qalloc(2)
        squin.rx(0.25, q[0])
        squin.rx(0.5, q[1])

    AggressiveUnroll(test.dialects).fixpoint(test)
    rule = _build_rule_keyed(test, attr_names_by_type={gate.stmts.Rx: ("angle",)})
    Walk(rule).rewrite(test.code)
    rxs = _gate_stmts(test, gate.stmts.Rx)
    assert len(rxs) == 2


def test_two_disjoint_cz_pairs_merge():
    @squin.kernel
    def test():
        q = squin.qalloc(4)
        squin.cz(q[0], q[1])
        squin.cz(q[2], q[3])

    AggressiveUnroll(test.dialects).fixpoint(test)
    rule = _build_rule_simple(test)
    Walk(rule).rewrite(test.code)

    czs = _gate_stmts(test, gate.stmts.CZ)
    assert len(czs) == 1
    ctrls_owner = czs[0].controls.owner
    targets_owner = czs[0].targets.owner
    assert isinstance(ctrls_owner, ilist.New)
    assert isinstance(targets_owner, ilist.New)
    assert len(ctrls_owner.values) == 2
    assert len(targets_owner.values) == 2


def test_phased_xz_with_matching_exponents_merges():
    @squin.kernel
    def test():
        q = squin.qalloc(2)
        x_exp = 0.5
        z_exp = 0.25
        ax_exp = 0.125
        squin.phased_xz(x_exp, z_exp, ax_exp, q[0])
        squin.phased_xz(x_exp, z_exp, ax_exp, q[1])

    AggressiveUnroll(test.dialects).fixpoint(test)
    rule = _build_rule_keyed(
        test,
        attr_names_by_type={
            gate.stmts.PhasedXZ: (
                "x_exponent",
                "z_exponent",
                "axis_phase_exponent",
            )
        },
    )
    Walk(rule).rewrite(test.code)

    pxz = _gate_stmts(test, gate.stmts.PhasedXZ)
    assert len(pxz) == 1
    assert isinstance(pxz[0].qubits.owner, ilist.New)
    assert len(pxz[0].qubits.owner.values) == 2


def _pierce(ids, inc, out, key, fixed=None, top=None):
    return pierce_into_fixed(ids, inc, out, key, fixed or {}, top or (len(ids) + 1))


def test_pierce_chain_strictly_increasing():
    # 0 -> 1 -> 2 dependency chain
    ids = [0, 1, 2]
    inc = {0: set(), 1: {0}, 2: {1}}
    out = {0: {1}, 1: {2}, 2: set()}
    key = {0: ("X",), 1: ("X",), 2: ("X",)}
    lv = _pierce(ids, inc, out, key)
    assert lv[0] < lv[1] < lv[2]


def test_pierce_independent_same_key_share_level():
    ids = [0, 1]
    inc = {0: set(), 1: set()}
    out = {0: set(), 1: set()}
    key = {0: ("X",), 1: ("X",)}
    lv = _pierce(ids, inc, out, key)
    assert lv[0] == lv[1]


def test_pierce_two_neighbouring_x_layers_merge():
    # 0 (X) independent; 1 (X) feeding a later Y (node 2). The two X still share
    # a level — the Y below doesn't pin them apart.
    ids = [0, 1, 2]
    inc = {0: set(), 1: set(), 2: {1}}
    out = {0: set(), 1: {2}, 2: set()}
    key = {0: ("X",), 1: ("X",), 2: ("Y",)}
    lv = _pierce(ids, inc, out, key)
    assert lv[0] == lv[1]


def test_pierce_fixed_wall_separates_gates():
    # 0 (X) -> wall W (fixed CZ) -> 1 (X). W is between them, so they cannot
    # share a level: 0 below the wall, 1 above.
    ids = [0, "W", 1]
    inc = {0: set(), "W": {0}, 1: {"W"}}
    out = {0: {"W"}, "W": {1}, 1: set()}
    key = {0: ("X",), "W": ("CZ",), 1: ("X",)}
    lv = pierce_into_fixed(ids, inc, out, key, {"W": 5}, top=10)
    assert lv["W"] == 5  # wall stays put
    assert lv[0] < 5 < lv[1]


def test_pierce_merges_past_idle_wall():
    # 0 (X) and 1 (X) independent; a fixed wall W that touches neither (their
    # qubits are idle there). They merge despite the wall existing.
    ids = [0, 1, "W"]
    inc = {0: set(), 1: set(), "W": set()}
    out = {0: set(), 1: set(), "W": set()}
    key = {0: ("X",), 1: ("X",), "W": ("CZ",)}
    lv = pierce_into_fixed(ids, inc, out, key, {"W": 5}, top=10)
    assert lv[0] == lv[1]
