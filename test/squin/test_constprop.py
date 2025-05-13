# These tests are used to verify the multiple
# result values from certain statements are handled properly
# in constant propagation. Originally a custom constprop
# method table had to be implemented but the newer version of
# Kirin has fixed this issue (:

from kirin import ir, types
from kirin.passes import Fold
from kirin.dialects import py, func
from kirin.analysis.const import Propagate

from bloqade import squin


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


def test_wire_apply_constprop():

    stmts = [
        (n_qubits := as_int(2)),
        (qreg := squin.qubit.New(n_qubits=n_qubits.result)),
        (idx0 := as_int(0)),
        (q0 := py.GetItem(qreg.result, idx0.result)),
        (idx1 := as_int(1)),
        (q1 := py.GetItem(qreg.result, idx1.result)),
        # get wires
        (w0 := squin.wire.Unwrap(q0.result)),
        (w1 := squin.wire.Unwrap(q1.result)),
        # put wire through gates
        (x := squin.op.stmts.X()),
        (cx := squin.op.stmts.Control(op=x.result, n_controls=1)),
        (a := squin.wire.Apply(cx.result, w0.result, w1.result)),
        (func.Return(a.results[0])),
    ]
    constructed_method = gen_func_from_stmts(stmts)

    prop_analysis = Propagate(constructed_method.dialects)
    frame, _ = prop_analysis.run_analysis(constructed_method)

    assert len(frame.entries.values()) == 13


def test_wire_broadcast_constprop():

    stmts = [
        (n_qubits := as_int(4)),
        (qreg := squin.qubit.New(n_qubits=n_qubits.result)),
        (idx0 := as_int(0)),
        (q0 := py.GetItem(qreg.result, idx0.result)),
        (idx1 := as_int(1)),
        (q1 := py.GetItem(qreg.result, idx1.result)),
        (idx2 := as_int(2)),
        (q2 := py.GetItem(qreg.result, idx2.result)),
        (idx3 := as_int(3)),
        (q3 := py.GetItem(qreg.result, idx3.result)),
        # get wires
        (w0 := squin.wire.Unwrap(q0.result)),
        (w1 := squin.wire.Unwrap(q1.result)),
        (w2 := squin.wire.Unwrap(q2.result)),
        (w3 := squin.wire.Unwrap(q3.result)),
        # put wire through gates
        (x := squin.op.stmts.X()),
        (cx := squin.op.stmts.Control(op=x.result, n_controls=1)),
        (
            a := squin.wire.Broadcast(
                cx.result, w0.result, w1.result, w2.result, w3.result
            )
        ),
        (func.Return(a.results[0])),
    ]
    constructed_method = gen_func_from_stmts(stmts)

    prop_analysis = Propagate(constructed_method.dialects)
    frame, _ = prop_analysis.run_analysis(constructed_method)

    assert len(frame.entries.values()) == 21
