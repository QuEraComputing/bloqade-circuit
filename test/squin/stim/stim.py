from kirin import ir, types
from kirin.dialects import py, func, ilist

import bloqade.squin.passes as squin_passes
from bloqade import qasm2, squin


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
        (op3 := squin.op.stmts.Identity(sites=1)),
        (op4 := squin.op.stmts.Identity(sites=1)),
        (v0 := squin.wire.Apply(op1.result, w0.result)),
        (v1 := squin.wire.Apply(op2.result, v0.results[0])),
        (v2 := squin.wire.Apply(op3.result, v1.results[0])),
        (v3 := squin.wire.Apply(op4.result, v2.results[0])),
        (
            squin.wire.Wrap(v3.results[0], q0.result)
        ),  # for wrap, just free a use for the result SSAval
        (ret_none := func.ConstantNone()),
        (func.Return(ret_none)),
        # the fact I return a wire here means DCE will NOT go ahead and
        # eliminate all the other wire.Apply stmts
    ]

    constructed_method = gen_func_from_stmts(stmts)

    constructed_method.print()

    squin_to_stim = squin_passes.SquinToStim(constructed_method.dialects)
    squin_to_stim(constructed_method)

    constructed_method.print()


def test_control():

    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(2)),
        (qreg := qasm2.core.QRegNew(n_qubits=n_qubits.result)),
        # Get qubis out
        (idx0 := as_int(0)),
        (q0 := qasm2.core.QRegGet(reg=qreg.result, idx=idx0.result)),
        (idx1 := as_int(1)),
        (q1 := qasm2.core.QRegGet(reg=qreg.result, idx=idx1.result)),
        # Unwrap to get wires
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        (w1 := squin.wire.Unwrap(qubit=q1.result)),
        # set up control gate
        (op1 := squin.op.stmts.X()),
        (cx := squin.op.stmts.Control(op1.result, n_controls=1)),
        (app := squin.wire.Apply(cx.result, w0.result, w1.result)),
        # wrap things back
        (squin.wire.Wrap(wire=app.results[0], qubit=q0.result)),
        (squin.wire.Wrap(wire=app.results[1], qubit=q1.result)),
        (ret_none := func.ConstantNone()),
        (func.Return(ret_none)),
    ]

    constructed_method = gen_func_from_stmts(stmts)
    constructed_method.print()

    squin_to_stim = squin_passes.SquinToStim(constructed_method.dialects)
    squin_to_stim(constructed_method)

    constructed_method.print()


test_control()
