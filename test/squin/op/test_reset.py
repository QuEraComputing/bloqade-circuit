from kirin import ir, types
from kirin.passes import Fold
from kirin.dialects import py, func

from bloqade import qasm2, squin
from bloqade.squin.wire import Unwrap, WireType


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
        signature=func.Signature(inputs=(), output=WireType),
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


def test_reset():
    stmts = [
        (n_qubits := as_int(1)),
        (qreg := qasm2.core.QRegNew(n_qubits=n_qubits.result)),
        (idx := as_int(0)),
        (qubit := qasm2.core.QRegGet(qreg.result, idx.result)),
        # extract wire
        (wire := Unwrap(qubit.result)),
        (reset := squin.op.stmts.Reset()),
        (app := squin.wire.Apply(reset.result, wire.result)),
        (func.Return(app.results[0])),
    ]

    constructed_method = gen_func_from_stmts(stmts)
    assert constructed_method.return_type == WireType
