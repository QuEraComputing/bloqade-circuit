import pytest
from kirin import ir, types
from kirin.passes import Fold
from kirin.dialects import py, func, ilist

from bloqade import qasm2, squin
from bloqade.squin import qubit
from bloqade.analysis import address


def as_int(value: int):
    return py.constant.Constant(value=value)


squin_with_qasm_core = squin.groups.wired.add(qasm2.core).add(ilist)


def test_unwrap():

    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(2)),
        (qreg := qasm2.core.QRegNew(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q1 := qasm2.core.QRegGet(reg=qreg.result, idx=idx0.result)),
        (idx1 := as_int(1)),
        (q2 := qasm2.core.QRegGet(reg=qreg.result, idx=idx1.result)),
        # Unwrap to get wires
        (w1 := squin.wire.Unwrap(qubit=q1.result)),
        (w2 := squin.wire.Unwrap(qubit=q2.result)),
        # Put them in an ilist and return to prevent elimination
        (wire_list := ilist.New([w1.result, w2.result])),
        (func.Return(wire_list)),
    ]

    block = ir.Block(stmts)
    block.args.append_from(types.MethodType[[], types.NoneType], "main_self")
    func_wrapper = func.Function(
        sym_name="main",
        signature=func.Signature(inputs=(), output=ilist.IListType),
        body=ir.Region(blocks=block),
    )

    constructed_method = ir.Method(
        mod=None,
        py_func=None,
        sym_name="main",
        dialects=squin_with_qasm_core,
        code=func_wrapper,
        arg_names=[],
    )

    fold_pass = Fold(squin_with_qasm_core)
    fold_pass(constructed_method)

    frame, _ = address.AddressAnalysis(constructed_method.dialects).run_analysis(
        constructed_method, no_raise=False
    )

    address_wires = []
    address_types = frame.entries.values()  # dict[SSAValue, Address]
    for address_type in address_types:
        if isinstance(address_type, address.AddressWire):
            address_wires.append(address_type)

    # 2 AddressWires should be produced from the Analysis
    assert len(address_wires) == 2
    # The AddressWires should have qubits 0 and 1 as their parents
    for qubit_idx, address_wire in enumerate(address_wires):
        assert qubit_idx == address_wire.origin_qubit.data


## test unwrap + pass through single statements
def test_multiple_unwrap():

    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(2)),
        (qreg := qasm2.core.QRegNew(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q0 := qasm2.core.QRegGet(reg=qreg.result, idx=idx0.result)),
        (idx1 := as_int(1)),
        (q1 := qasm2.core.QRegGet(reg=qreg.result, idx=idx1.result)),
        # Unwrap to get wires
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        (w1 := squin.wire.Unwrap(qubit=q1.result)),
        # pass the wires through some 1 Qubit operators
        (op1 := squin.op.stmts.T()),
        (op2 := squin.op.stmts.H()),
        (op3 := squin.op.stmts.X()),
        (v0 := squin.wire.Apply(op1.result, w0.result)),
        (v1 := squin.wire.Apply(op2.result, v0.results[0])),
        (v2 := squin.wire.Apply(op3.result, w1.result)),
        (wire_list := ilist.New([v1.results[0], v2.results[0]])),
        (func.Return(wire_list)),
    ]

    block = ir.Block(stmts)
    block.args.append_from(types.MethodType[[], types.NoneType], "main_self")
    func_wrapper = func.Function(
        sym_name="main",
        signature=func.Signature(inputs=(), output=ilist.IListType),
        body=ir.Region(blocks=block),
    )

    constructed_method = ir.Method(
        mod=None,
        py_func=None,
        sym_name="main",
        dialects=squin_with_qasm_core,
        code=func_wrapper,
        arg_names=[],
    )

    fold_pass = Fold(squin_with_qasm_core)
    fold_pass(constructed_method)

    frame, _ = address.AddressAnalysis(constructed_method.dialects).run_analysis(
        constructed_method, no_raise=False
    )

    address_wire_parent_qubit_0 = []
    address_wire_parent_qubit_1 = []
    address_types = frame.entries.values()  # dict[SSAValue, Address]
    for address_type in address_types:
        if isinstance(address_type, address.AddressWire):
            if address_type.origin_qubit.data == 0:
                address_wire_parent_qubit_0.append(address_type)
            elif address_type.origin_qubit.data == 1:
                address_wire_parent_qubit_1.append(address_type)

    # there should be 3 AddressWire instances with parent qubit 0
    # and 2 AddressWire instances with parent qubit 1
    assert len(address_wire_parent_qubit_0) == 3
    assert len(address_wire_parent_qubit_1) == 2


def test_multiple_wire_apply():

    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(2)),
        (qreg := qasm2.core.QRegNew(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q0 := qasm2.core.QRegGet(reg=qreg.result, idx=idx0.result)),
        (idx1 := as_int(1)),
        (q1 := qasm2.core.QRegGet(reg=qreg.result, idx=idx1.result)),
        # Unwrap to get wires
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        (w1 := squin.wire.Unwrap(qubit=q1.result)),
        # Put the wires through a 2Q operator
        (op1 := squin.op.stmts.X()),
        (op2 := squin.op.stmts.Control(op1.result, n_controls=1)),
        (apply_stmt := squin.wire.Apply(op2.result, w0.result, w1.result)),
        # Inside constant prop, in eval_statement in the forward data analysis,
        # Apply is marked as pure so frame.get_values(SSAValues) -> ValueType (where)
        (wire_list := ilist.New([apply_stmt.results[0], apply_stmt.results[1]])),
        (func.Return(wire_list.result)),
    ]

    block = ir.Block(stmts)
    block.args.append_from(types.MethodType[[], types.NoneType], "main_self")
    func_wrapper = func.Function(
        sym_name="main",
        signature=func.Signature(inputs=(), output=ilist.IListType),
        body=ir.Region(blocks=block),
    )

    constructed_method = ir.Method(
        mod=None,
        py_func=None,
        sym_name="main",
        dialects=squin_with_qasm_core,
        code=func_wrapper,
        arg_names=[],
    )

    fold_pass = Fold(squin_with_qasm_core)
    fold_pass(constructed_method)

    # const_prop = const.Propagate(squin_with_qasm_core)
    # frame, _ = const_prop.run_analysis(method=constructed_method, no_raise=False)

    frame, _ = address.AddressAnalysis(constructed_method.dialects).run_analysis(
        constructed_method, no_raise=False
    )

    address_wire_parent_qubit_0 = []
    address_wire_parent_qubit_1 = []
    address_types = frame.entries.values()  # dict[SSAValue, Address]
    for address_type in address_types:
        if isinstance(address_type, address.AddressWire):
            if address_type.origin_qubit.data == 0:
                address_wire_parent_qubit_0.append(address_type)
            elif address_type.origin_qubit.data == 1:
                address_wire_parent_qubit_1.append(address_type)

    # Should be 2 AddressWire instances with origin qubit 0
    # and another 2 with origin qubit 1
    assert len(address_wire_parent_qubit_0) == 2
    assert len(address_wire_parent_qubit_1) == 2


def test_slice():

    @squin.kernel
    def main():
        q = qubit.new(4)
        # get the middle qubits out and apply to them
        sub_q = q[1:3]
        qubit.broadcast(squin.op.x(), sub_q)
        # get a single qubit out, do some stuff
        single_q = sub_q[0]
        qubit.apply(squin.op.h(), single_q)

    address_analysis = address.AddressAnalysis(main.dialects)
    frame, _ = address_analysis.run_analysis(main, no_raise=False)

    address_regs = [
        address_reg_type
        for address_reg_type in frame.entries.values()
        if isinstance(address_reg_type, address.AddressReg)
    ]
    address_qubits = [
        address_qubit_type
        for address_qubit_type in frame.entries.values()
        if isinstance(address_qubit_type, address.AddressQubit)
    ]

    assert address_regs[0] == address.AddressReg(data=range(0, 4))
    assert address_regs[1] == address.AddressReg(data=range(1, 3))

    assert address_qubits[0] == address.AddressQubit(data=1)


def test_for_loop():
    @squin.kernel
    def main():
        q = squin.qubit.new(3)
        x = squin.op.kron(squin.op.identity(sites=2), squin.op.x())
        for i in range(3):
            squin.qubit.apply(x, q)

        return q

    address_analysis = address.AddressAnalysis(main.dialects)
    address_analysis.run_analysis(main, no_raise=False)


@pytest.mark.xfail  # fails due to bug in for loop variable, see issue kirin#408
def test_for_loop_idx():
    @squin.kernel
    def main():
        q = squin.qubit.new(3)
        x = squin.op.x()
        for i in range(3):
            squin.qubit.apply(x, [q[i]])

        return q

    main.print()

    address_analysis = address.AddressAnalysis(main.dialects)
    address_analysis.run_analysis(main, no_raise=False)
