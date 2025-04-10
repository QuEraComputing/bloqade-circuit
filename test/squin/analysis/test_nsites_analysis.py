from kirin import ir, types
from kirin.passes import Fold
from kirin.dialects import py, func

from bloqade import squin
from bloqade.squin.analysis import nsites


def as_int(value: int):
    return py.constant.Constant(value=value)


def as_float(value: float):
    return py.constant.Constant(value=value)


def gen_func_from_stmts(stmts):

    squin_with_py = squin.groups.wired.add(py)

    block = ir.Block(stmts)
    block.args.append_from(types.MethodType[[], types.NoneType], "main_self")
    func_wrapper = func.Function(
        sym_name="main",
        signature=func.Signature(inputs=(), output=squin.op.types.OpType),
        body=ir.Region(blocks=block),
    )

    constructed_method = ir.Method(
        mod=None,
        py_func=None,
        sym_name="main",
        dialects=squin_with_py,
        code=func_wrapper,
        arg_names=[],
    )

    fold_pass = Fold(squin_with_py)
    fold_pass(constructed_method)

    return constructed_method


def test_primitive_ops():
    # test a couple standard operators derived from PrimitiveOp

    stmts = [
        (n_qubits := as_int(1)),
        (qreg := squin.qubit.New(n_qubits=n_qubits.result)),
        (idx0 := as_int(0)),
        (q := py.GetItem(qreg.result, idx0.result)),
        # get wire
        (w := squin.wire.Unwrap(q.result)),
        # put wire through gates
        (h := squin.op.stmts.H()),
        (t := squin.op.stmts.T()),
        (x := squin.op.stmts.X()),
        (v0 := squin.wire.Apply(h.result, w.result)),
        (v1 := squin.wire.Apply(t.result, v0.results[0])),
        (v2 := squin.wire.Apply(x.result, v1.results[0])),
        (func.Return(v2.results[0])),
    ]

    constructed_method = gen_func_from_stmts(stmts)

    nsites_frame, _ = nsites.NSitesAnalysis(constructed_method.dialects).run_analysis(
        constructed_method, no_raise=False
    )

    has_n_sites = []
    for nsites_type in nsites_frame.entries.values():
        if isinstance(nsites_type, nsites.NumberSites):
            has_n_sites.append(nsites_type)
            assert nsites_type.sites == 1

    assert len(has_n_sites) == 3


# Kron, Mult, Control, Rot, and Scale all have methods defined for handling them in impls,
# The following should ensure the code paths are properly exercised


def test_control():
    # Control doesn't have an impl but it is handled in the eval_stmt of the interpreter
    # because it has a HasNSitesTrait future statements might have

    stmts: list[ir.Statement] = [
        (h0 := squin.op.stmts.H()),
        (controlled_h := squin.op.stmts.Control(op=h0.result, n_controls=1)),
        (func.Return(controlled_h.result)),
    ]

    constructed_method = gen_func_from_stmts(stmts)

    nsites_frame, _ = nsites.NSitesAnalysis(constructed_method.dialects).run_analysis(
        constructed_method, no_raise=False
    )

    has_n_sites = []
    for nsites_type in nsites_frame.entries.values():
        if isinstance(nsites_type, nsites.NumberSites):
            has_n_sites.append(nsites_type)

    assert len(has_n_sites) == 2
    assert has_n_sites[0].sites == 1
    assert has_n_sites[1].sites == 2


def test_kron():

    stmts: list[ir.Statement] = [
        (h0 := squin.op.stmts.H()),
        (h1 := squin.op.stmts.H()),
        (hh := squin.op.stmts.Kron(h0.result, h1.result)),
        (func.Return(hh.result)),
    ]

    constructed_method = gen_func_from_stmts(stmts)

    nsites_frame, _ = nsites.NSitesAnalysis(constructed_method.dialects).run_analysis(
        constructed_method, no_raise=False
    )

    has_n_sites = []
    for nsites_type in nsites_frame.entries.values():
        if isinstance(nsites_type, nsites.NumberSites):
            has_n_sites.append(nsites_type)

    assert len(has_n_sites) == 3
    assert has_n_sites[0].sites == 1
    assert has_n_sites[1].sites == 1
    assert has_n_sites[2].sites == 2


def test_mult_square_same_sites():
    # Ensure that two operators of the same size produce
    # a valid operator as their result

    stmts: list[ir.Statement] = [
        (h0 := squin.op.stmts.H()),
        (h1 := squin.op.stmts.H()),
        (h2 := squin.op.stmts.Mult(h0.result, h1.result)),
        (func.Return(h2.result)),
    ]

    constructed_method = gen_func_from_stmts(stmts)

    nsites_frame, _ = nsites.NSitesAnalysis(constructed_method.dialects).run_analysis(
        constructed_method, no_raise=False
    )

    has_n_sites = []
    for nsites_type in nsites_frame.entries.values():
        if isinstance(nsites_type, nsites.NumberSites):
            has_n_sites.append(nsites_type)

    # should be three HasNSites types
    assert len(has_n_sites) == 3
    # the first 2 HasNSites will have 1 site but
    # the Kron-produced operator should have 2 sites
    assert has_n_sites[0].sites == 1
    assert has_n_sites[1].sites == 1
    assert has_n_sites[2].sites == 2


def test_mult_square_different_sites():
    # Ensure that two operators of different sizes produce
    # NoSites as a type. Note that a better solution would be
    # to implement a special error type in the type lattice
    # but this would introduce some complexity later on

    stmts: list[ir.Statement] = [
        (h0 := squin.op.stmts.H()),
        (h1 := squin.op.stmts.H()),
        # Kron to make nsites = 2 operator
        (hh := squin.op.stmts.Kron(h0.result, h1.result)),
        # apply Mult on HasNSites(2) and HasNSites(1)
        (invalid_op := squin.op.stmts.Mult(hh.result, h1.result)),
        (func.Return(invalid_op.result)),
    ]

    constructed_method = gen_func_from_stmts(stmts)

    nsites_frame, _ = nsites.NSitesAnalysis(constructed_method.dialects).run_analysis(
        constructed_method, no_raise=False
    )

    nsites_types = list(nsites_frame.entries.values())

    has_n_sites = []
    no_sites = []
    for nsite_type in nsites_types:
        if isinstance(nsite_type, nsites.NumberSites):
            has_n_sites.append(nsite_type)
        elif isinstance(nsite_type, nsites.NoSites):
            no_sites.append(nsite_type)

    assert len(has_n_sites) == 3
    # HasNSites(1) for Hadamards, 2 for Kron result
    assert has_n_sites[0].sites == 1
    assert has_n_sites[1].sites == 1
    assert has_n_sites[2].sites == 2
    # One from function itself, another from invalid mult
    assert len(no_sites) == 2


def test_rot():

    stmts: list[ir.Statement] = [
        (h0 := squin.op.stmts.H()),
        (angle := as_float(0.2)),
        (rot_h := squin.op.stmts.Rot(axis=h0.result, angle=angle.result)),
        (func.Return(rot_h.result)),
    ]

    constructed_method = gen_func_from_stmts(stmts)

    nsites_frame, _ = nsites.NSitesAnalysis(constructed_method.dialects).run_analysis(
        constructed_method, no_raise=False
    )

    has_n_sites = []
    for nsites_type in nsites_frame.entries.values():
        if isinstance(nsites_type, nsites.NumberSites):
            has_n_sites.append(nsites_type)

    assert len(has_n_sites) == 2
    # Rot should just propagate whatever Sites type is there
    assert has_n_sites[0].sites == 1
    assert has_n_sites[1].sites == 1


def test_scale():

    stmts: list[ir.Statement] = [
        (h0 := squin.op.stmts.H()),
        (factor := as_float(0.2)),
        (rot_h := squin.op.stmts.Scale(op=h0.result, factor=factor.result)),
        (func.Return(rot_h.result)),
    ]

    constructed_method = gen_func_from_stmts(stmts)

    nsites_frame, _ = nsites.NSitesAnalysis(constructed_method.dialects).run_analysis(
        constructed_method, no_raise=False
    )

    has_n_sites = []
    for nsites_type in nsites_frame.entries.values():
        if isinstance(nsites_type, nsites.NumberSites):
            has_n_sites.append(nsites_type)

    assert len(has_n_sites) == 2
    # Rot should just propagate whatever Sites type is there
    assert has_n_sites[0].sites == 1
    assert has_n_sites[1].sites == 1
