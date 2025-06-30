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
        constructed_method
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

    # set fold to False to avoid things getting removed
    @squin.kernel(fold=False)
    def test():
        h = squin.op.h()
        controlled_h = squin.op.control(op=h, n_controls=1)  # noqa: F841

    nsites_frame, _ = nsites.NSitesAnalysis(test.dialects).run_analysis(test)

    has_n_sites = []
    for nsites_type in nsites_frame.entries.values():
        if isinstance(nsites_type, nsites.NumberSites):
            has_n_sites.append(nsites_type)

    assert len(has_n_sites) == 2
    assert has_n_sites[0].sites == 1
    assert has_n_sites[1].sites == 2


def test_kron():
    @squin.kernel(fold=False)
    def test():
        h0 = squin.op.h()
        h1 = squin.op.h()
        hh = squin.op.kron(h0, h1)  # noqa: F841

    nsites_frame, _ = nsites.NSitesAnalysis(test.dialects).run_analysis(test)

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
    @squin.kernel(fold=False)
    def test():
        h0 = squin.op.h()
        h1 = squin.op.h()
        h2 = squin.op.mult(h0, h1)  # noqa: F841

    nsites_frame, _ = nsites.NSitesAnalysis(test.dialects).run_analysis(test)

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
    @squin.kernel(fold=False)
    def test():
        h0 = squin.op.h()
        h1 = squin.op.h()
        # Kron to make nsites = 2 operator
        hh = squin.op.kron(h0, h1)  # noqa: F841
        # apply Mult on HasNSites(2) and HasNSites(1)
        invalid_op = squin.op.mult(hh, h1)  # noqa: F841

    nsites_frame, _ = nsites.NSitesAnalysis(test.dialects).run_analysis(test)

    nsites_types = list(nsites_frame.entries.values())

    has_n_sites = []
    no_sites = []
    for nsite_type in nsites_types:
        if isinstance(nsite_type, nsites.NumberSites):
            has_n_sites.append(nsite_type)
        elif isinstance(nsite_type, nsites.NoSites):
            no_sites.append(nsite_type)

    # HasNSites(1) for Hadamards, 2 for Kron result
    assert len(has_n_sites) == 3
    assert has_n_sites[0].sites == 1
    assert has_n_sites[1].sites == 1
    assert has_n_sites[2].sites == 2
    # One from function itself, another from invalid mult
    assert len(no_sites) == 2


def test_rot():
    # Rot should just propagate whatever Sites type is there
    @squin.kernel(fold=False)
    def test():
        h0 = squin.op.h()
        angle = 0.2
        rot_h = squin.op.rot(axis=h0, angle=angle)  # noqa: F841

    nsites_frame, _ = nsites.NSitesAnalysis(test.dialects).run_analysis(test)

    has_n_sites = []
    for nsites_type in nsites_frame.entries.values():
        if isinstance(nsites_type, nsites.NumberSites):
            has_n_sites.append(nsites_type)

    assert len(has_n_sites) == 2
    # Rot should just propagate whatever Sites type is there
    assert has_n_sites[0].sites == 1
    assert has_n_sites[1].sites == 1


def test_scale():
    # Scale should just propagate whatever Sites type is there
    @squin.kernel(fold=False)
    def test():
        h0 = squin.op.h()
        factor = 0.2
        scaled_h = squin.op.scale(op=h0, factor=factor)  # noqa: F841

    nsites_frame, _ = nsites.NSitesAnalysis(test.dialects).run_analysis(test)

    has_n_sites = []
    for nsites_type in nsites_frame.entries.values():
        if isinstance(nsites_type, nsites.NumberSites):
            has_n_sites.append(nsites_type)

    assert len(has_n_sites) == 2
    assert has_n_sites[0].sites == 1
    assert has_n_sites[1].sites == 1


def test_invoke():

    @squin.kernel(fold=False)
    def test():

        # use cx wrapper, ends up as an invoke in the program
        q = squin.qubit.new(4)

        squin.qubit.apply(squin.op.h(), q[0])
        squin.qubit.apply(squin.op.cx(), q[0], q[1])
        squin.qubit.apply(squin.op.cx(), q[0], q[2])
        squin.qubit.apply(squin.op.cx(), q[0], q[3])
        squin.qubit.broadcast(squin.op.cx(), q)

    nsites_frame, _ = nsites.NSitesAnalysis(test.dialects).run_analysis(test)

    has_n_sites = []
    for nsites_type in nsites_frame.entries.values():
        if isinstance(nsites_type, nsites.NumberSites):
            has_n_sites.append(nsites_type)

    assert len(has_n_sites) == 5
    assert has_n_sites[0].sites == 1
    for n_site in has_n_sites[1:]:
        assert n_site.sites == 2
