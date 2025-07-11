import os

from kirin import ir, types
from kirin.passes import TypeInfer
from kirin.rewrite import Walk
from kirin.dialects import py, func

from bloqade import squin
from bloqade.squin import wire, kernel
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass
from bloqade.squin.rewrite import WrapAddressAnalysis
from bloqade.analysis.address import AddressAnalysis


def gen_func_from_stmts(stmts, output_type=types.NoneType):

    extended_dialect = kernel.add(wire)

    block = ir.Block(stmts)
    block.args.append_from(types.MethodType[[], types.NoneType], "main")
    func_wrapper = func.Function(
        sym_name="main",
        signature=func.Signature(inputs=(), output=output_type),
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


def codegen(mt: ir.Method):
    # method should not have any arguments!
    emit = EmitStimMain()
    emit.initialize()
    emit.run(mt=mt, args=())
    return emit.get_output()


def as_int(value: int):
    return py.constant.Constant(value=value)


def as_float(value: float):
    return py.constant.Constant(value=value)


def get_stim_reference_file(filename: str) -> str:
    path = os.path.join(
        os.path.dirname(__file__),
        "stim_reference_programs",
        "wire",
        filename,
    )
    with open(path, "r") as f:
        return f.read()


def run_passes(test_method):
    TypeInfer(test_method.dialects)(test_method)
    addr_frame, _ = AddressAnalysis(test_method.dialects).run_analysis(test_method)
    Walk(WrapAddressAnalysis(address_analysis=addr_frame.entries)).rewrite(
        test_method.code
    )
    SquinToStimPass(test_method.dialects)(test_method)


def test_wire():
    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(4)),
        # returns an ilist
        (q := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q0 := py.indexing.GetItem(q.result, idx0.result)),
        (idx1 := as_int(1)),
        (q1 := py.indexing.GetItem(q.result, idx1.result)),
        (idx2 := as_int(2)),
        (q2 := py.indexing.GetItem(q.result, idx2.result)),
        (idx3 := as_int(3)),
        (q3 := py.indexing.GetItem(q.result, idx3.result)),
        # get wires from qubits
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        (w1 := squin.wire.Unwrap(qubit=q1.result)),
        (w2 := squin.wire.Unwrap(qubit=q2.result)),
        (w3 := squin.wire.Unwrap(qubit=q3.result)),
        # try Apply
        (op0 := squin.op.stmts.S()),
        (app0 := squin.wire.Apply(op0.result, w0.result)),
        # try Broadcast
        (op1 := squin.op.stmts.H()),
        (
            broad0 := squin.wire.Broadcast(
                op1.result, app0.results[0], w1.result, w2.result, w3.result
            )
        ),
        # wrap everything back
        (squin.wire.Wrap(broad0.results[0], q0.result)),
        (squin.wire.Wrap(broad0.results[1], q1.result)),
        (squin.wire.Wrap(broad0.results[2], q2.result)),
        (squin.wire.Wrap(broad0.results[3], q3.result)),
        (ret_none := func.ConstantNone()),
        (func.Return(ret_none)),
    ]

    test_method = gen_func_from_stmts(stmts)
    run_passes(test_method)
    base_stim_prog = get_stim_reference_file("wire.stim")
    assert codegen(test_method) == base_stim_prog.rstrip()


def test_wire_apply():
    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(1)),
        (q := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubit out
        (idx0 := as_int(0)),
        (q0 := py.indexing.GetItem(q.result, idx0.result)),
        # Unwrap to get wires
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        # pass the wires through some 1 Qubit operators
        (op1 := squin.op.stmts.S()),
        (v0 := squin.wire.Apply(op1.result, w0.result)),
        (
            squin.wire.Wrap(v0.results[0], q0.result)
        ),  # for wrap, just free a use for the result SSAval
        (ret_none := func.ConstantNone()),
        (func.Return(ret_none)),
    ]

    test_method = gen_func_from_stmts(stmts)
    run_passes(test_method)
    base_stim_prog = get_stim_reference_file("wire_apply.stim")
    assert codegen(test_method) == base_stim_prog.rstrip()


def test_wire_multiple_apply():
    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(1)),
        (q := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubit out
        (idx0 := as_int(0)),
        (q0 := py.indexing.GetItem(q.result, idx0.result)),
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
    ]

    test_method = gen_func_from_stmts(stmts)
    run_passes(test_method)
    base_stim_prog = get_stim_reference_file("wire_multiple_apply.stim")
    assert codegen(test_method) == base_stim_prog.rstrip()


def test_wire_broadcast():
    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(4)),
        (q := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q0 := py.indexing.GetItem(q.result, idx0.result)),
        (idx1 := as_int(1)),
        (q1 := py.indexing.GetItem(q.result, idx1.result)),
        (idx2 := as_int(2)),
        (q2 := py.indexing.GetItem(q.result, idx2.result)),
        (idx3 := as_int(3)),
        (q3 := py.indexing.GetItem(q.result, idx3.result)),
        # Unwrap to get wires
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        (w1 := squin.wire.Unwrap(qubit=q1.result)),
        (w2 := squin.wire.Unwrap(qubit=q2.result)),
        (w3 := squin.wire.Unwrap(qubit=q3.result)),
        # Apply with stim semantics
        (h_op := squin.op.stmts.H()),
        (
            app_res := squin.wire.Broadcast(
                h_op.result, w0.result, w1.result, w2.result, w3.result
            )
        ),
        # Wrap everything back
        (squin.wire.Wrap(app_res.results[0], q0.result)),
        (squin.wire.Wrap(app_res.results[1], q1.result)),
        (squin.wire.Wrap(app_res.results[2], q2.result)),
        (squin.wire.Wrap(app_res.results[3], q3.result)),
        (ret_none := func.ConstantNone()),
        (func.Return(ret_none)),
    ]

    test_method = gen_func_from_stmts(stmts)
    run_passes(test_method)
    base_stim_prog = get_stim_reference_file("wire_broadcast.stim")
    assert codegen(test_method) == base_stim_prog.rstrip()


def test_wire_broadcast_control():
    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(4)),
        (q := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q0 := py.indexing.GetItem(q.result, idx0.result)),
        (idx1 := as_int(1)),
        (q1 := py.indexing.GetItem(q.result, idx1.result)),
        (idx2 := as_int(2)),
        (q2 := py.indexing.GetItem(q.result, idx2.result)),
        (idx3 := as_int(3)),
        (q3 := py.indexing.GetItem(q.result, idx3.result)),
        # Unwrap to get wires
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        (w1 := squin.wire.Unwrap(qubit=q1.result)),
        (w2 := squin.wire.Unwrap(qubit=q2.result)),
        (w3 := squin.wire.Unwrap(qubit=q3.result)),
        # Create and apply CX gate
        (x_op := squin.op.stmts.X()),
        (ctrl_x_op := squin.op.stmts.Control(x_op.result, n_controls=1)),
        (
            app_res := squin.wire.Broadcast(
                ctrl_x_op.result, w0.result, w1.result, w2.result, w3.result
            )
        ),
        # measure it all out
        (squin.wire.Measure(wire=app_res.results[0], qubit=q0.result)),
        (squin.wire.Measure(wire=app_res.results[1], qubit=q1.result)),
        (squin.wire.Measure(wire=app_res.results[2], qubit=q2.result)),
        (squin.wire.Measure(wire=app_res.results[3], qubit=q3.result)),
        (ret_none := func.ConstantNone()),
        (func.Return(ret_none)),
    ]

    test_method = gen_func_from_stmts(stmts)
    run_passes(test_method)
    base_stim_prog = get_stim_reference_file("wire_broadcast_control.stim")
    assert codegen(test_method) == base_stim_prog.rstrip()


def test_wire_apply_control():
    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(2)),
        (q := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubis out
        (idx0 := as_int(0)),
        (q0 := py.indexing.GetItem(q.result, idx0.result)),
        (idx1 := as_int(1)),
        (q1 := py.indexing.GetItem(q.result, idx1.result)),
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

    test_method = gen_func_from_stmts(stmts)
    run_passes(test_method)
    base_stim_prog = get_stim_reference_file("wire_apply_control.stim")
    assert codegen(test_method) == base_stim_prog.rstrip()


def test_wire_measure():
    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(2)),
        (q := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubis out
        (idx0 := as_int(0)),
        (q0 := py.indexing.GetItem(q.result, idx0.result)),
        # Unwrap to get wires
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        # measure the wires out
        (squin.wire.Measure(wire=w0.result, qubit=q0.result)),
        (ret_none := func.ConstantNone()),
        (func.Return(ret_none)),
    ]

    test_method = gen_func_from_stmts(stmts)
    run_passes(test_method)
    base_stim_prog = get_stim_reference_file("wire_measure.stim")
    assert codegen(test_method) == base_stim_prog.rstrip()


def test_wire_reset():
    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(1)),
        (q := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q0 := py.indexing.GetItem(q.result, idx0.result)),
        # get wire
        (w0 := squin.wire.Unwrap(q0.result)),
        (res_op := squin.op.stmts.Reset()),
        (app := squin.wire.Apply(res_op.result, w0.result)),
        # wrap it back
        (squin.wire.Measure(wire=app.results[0], qubit=q0.result)),
        (ret_none := func.ConstantNone()),
        (func.Return(ret_none)),
    ]

    test_method = gen_func_from_stmts(stmts)
    run_passes(test_method)
    base_stim_prog = get_stim_reference_file("wire_reset.stim")
    assert codegen(test_method) == base_stim_prog.rstrip()


def test_wire_qubit_loss():

    stmts: list[ir.Statement] = [
        (n_qubits := as_int(5)),
        (q := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q0 := py.indexing.GetItem(q.result, idx0.result)),
        (idx1 := as_int(1)),
        (q1 := py.indexing.GetItem(q.result, idx1.result)),
        (idx2 := as_int(2)),
        (q2 := py.indexing.GetItem(q.result, idx2.result)),
        (idx3 := as_int(3)),
        (q3 := py.indexing.GetItem(q.result, idx3.result)),
        (idx4 := as_int(4)),
        (q4 := py.indexing.GetItem(q.result, idx4.result)),
        # get wires from qubits
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        (w1 := squin.wire.Unwrap(qubit=q1.result)),
        (w2 := squin.wire.Unwrap(qubit=q2.result)),
        (w3 := squin.wire.Unwrap(qubit=q3.result)),
        (w4 := squin.wire.Unwrap(qubit=q4.result)),
        (p_loss_0 := as_float(0.1)),
        # apply and broadcast qubit loss
        (ql_loss_0 := squin.noise.stmts.QubitLoss(p=p_loss_0.result)),
        (
            app_0 := squin.wire.Broadcast(
                ql_loss_0.result, w0.result, w1.result, w2.result, w3.result, w4.result
            )
        ),
        (p_loss_1 := as_float(0.9)),
        (ql_loss_1 := squin.noise.stmts.QubitLoss(p=p_loss_1.result)),
        (app_1 := squin.wire.Apply(ql_loss_1.result, app_0.results[0])),
        # wrap everything back
        (squin.wire.Measure(wire=app_1.results[0], qubit=q0.result)),
        (squin.wire.Measure(wire=app_0.results[1], qubit=q1.result)),
        (squin.wire.Measure(wire=app_0.results[2], qubit=q2.result)),
        (squin.wire.Measure(wire=app_0.results[3], qubit=q3.result)),
        (squin.wire.Measure(wire=app_0.results[4], qubit=q4.result)),
        (ret_none := func.ConstantNone()),
        (func.Return(ret_none)),
    ]

    test_method = gen_func_from_stmts(stmts)
    run_passes(test_method)
    base_stim_prog = get_stim_reference_file("wire_qubit_loss.stim")
    assert codegen(test_method) == base_stim_prog.rstrip()
