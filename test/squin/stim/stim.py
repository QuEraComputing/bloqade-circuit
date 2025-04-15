from kirin import ir, types
from kirin.passes import Fold
from kirin.rewrite import Walk, Fixpoint, DeadCodeElimination
from kirin.dialects import py, func, ilist

from bloqade import qasm2, squin
from bloqade.analysis import address
from bloqade.squin.rewrite import SquinToStim, WrapSquinAnalysis
from bloqade.squin.analysis import nsites


def as_int(value: int):
    return py.constant.Constant(value=value)


def as_float(value: float):
    return py.constant.Constant(value=value)


def gen_func_from_stmts(stmts):

    extended_dialect = squin.groups.wired.add(qasm2.core).add(ilist)

    block = ir.Block(stmts)
    block.args.append_from(types.MethodType[[], types.NoneType], "main_self")
    func_wrapper = func.Function(
        sym_name="main",
        signature=func.Signature(inputs=(), output=types.NoneType),
        body=ir.Region(blocks=block),
    )

    constructed_method = ir.Method(
        mod=None,
        py_func=None,
        sym_name="main",
        dialects=extended_dialect,
        code=func_wrapper,
        arg_names=[],
    )

    fold_pass = Fold(extended_dialect)
    fold_pass(constructed_method)

    return constructed_method


def test_1q():

    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(1)),
        (qreg := qasm2.core.QRegNew(n_qubits=n_qubits.result)),
        # Get qubit out
        (idx0 := as_int(0)),
        (q0 := qasm2.core.QRegGet(reg=qreg.result, idx=idx0.result)),
        # Unwrap to get wires
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        # pass the wires through some 1 Qubit operators
        (op1 := squin.op.stmts.S()),
        (op2 := squin.op.stmts.H()),
        (op3 := squin.op.stmts.X()),
        (v0 := squin.wire.Apply(op1.result, w0.result)),
        (v1 := squin.wire.Apply(op2.result, v0.results[0])),
        (v2 := squin.wire.Apply(op3.result, v1.results[0])),
        (
            squin.wire.Wrap(v2.results[0], q0.result)
        ),  # for wrap, just free a use for the result SSAval
        (ret_none := func.ConstantNone()),
        (func.Return(ret_none)),
        # the fact I return a wire here means DCE will NOT go ahead and
        # eliminate all the other wire.Apply stmts
    ]

    constructed_method = gen_func_from_stmts(stmts)

    constructed_method.print()

    address_frame, _ = address.AddressAnalysis(
        constructed_method.dialects
    ).run_analysis(constructed_method, no_raise=False)

    nsites_frame, _ = nsites.NSitesAnalysis(constructed_method.dialects).run_analysis(
        constructed_method, no_raise=False
    )

    constructed_method.print(analysis=address_frame.entries)
    constructed_method.print(analysis=nsites_frame.entries)

    # attempt to wrap analysis results

    wrap_squin_analysis = WrapSquinAnalysis(
        address_analysis=address_frame.entries, op_site_analysis=nsites_frame.entries
    )
    fix_walk_squin_analysis = Fixpoint(Walk(wrap_squin_analysis))
    rewrite_res = fix_walk_squin_analysis.rewrite(constructed_method.code)

    # attempt rewrite to Stim
    # Be careful with Fixpoint, can go to infinity until reaches defined threshold
    squin_to_stim = Walk(SquinToStim())
    rewrite_res = squin_to_stim.rewrite(constructed_method.code)

    # Get rid of the unused statements
    dce = Fixpoint(Walk(DeadCodeElimination()))
    rewrite_res = dce.rewrite(constructed_method.code)
    print(rewrite_res)

    constructed_method.print()


test_1q()
