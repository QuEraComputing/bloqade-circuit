from util import collect_address_types
from kirin import ir, types
from kirin.passes import Fold
from kirin.dialects import py, func, ilist

from bloqade import squin
from bloqade.analysis import address


def as_int(value: int):
    return py.constant.Constant(value=value)


squin_qubit_with_wire = squin.groups.wired.add(squin.qubit)


def build_method(stmts, dialects, output_type):
    block = ir.Block(stmts)
    block.args.append_from(types.MethodType[[], types.NoneType], "main_self")
    func_wrapper = func.Function(
        sym_name="main",
        signature=func.Signature(inputs=(), output=output_type),
        body=ir.Region(blocks=block),
    )
    return ir.Method(
        mod=None,
        py_func=None,
        sym_name="main",
        dialects=dialects,
        code=func_wrapper,
        arg_names=[],
    )


def run_fold_and_address_analysis(method):
    fold_pass = Fold(method.dialects)
    fold_pass(method)
    frame, _ = address.AddressAnalysis(method.dialects).run_analysis(
        method, no_raise=False
    )
    return frame


def test_unwrap():

    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(2)),
        (qreg := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (
            q1 := py.GetItem(
                index=idx0.result,
                obj=qreg.result,
            )
        ),
        (idx1 := as_int(1)),
        (
            q2 := py.GetItem(
                index=idx1.result,
                obj=qreg.result,
            )
        ),
        # Unwrap to get wires
        (w1 := squin.wire.Unwrap(qubit=q1.result)),
        (w2 := squin.wire.Unwrap(qubit=q2.result)),
        # Put them in an ilist and return to prevent elimination
        (wire_list := ilist.New([w1.result, w2.result])),
        (func.Return(wire_list)),
    ]

    method = build_method(stmts, squin_qubit_with_wire, ilist.IListType)
    frame = run_fold_and_address_analysis(method)
    address_wires = collect_address_types(frame, address.AddressWire)

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
        (qreg := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q0 := py.GetItem(index=idx0.result, obj=qreg.result)),
        (idx1 := as_int(1)),
        (q1 := py.GetItem(index=idx1.result, obj=qreg.result)),
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

    method = build_method(stmts, squin_qubit_with_wire, ilist.IListType)
    frame = run_fold_and_address_analysis(method)

    address_wire_parent_qubit_0 = []
    address_wire_parent_qubit_1 = []
    for address_type in collect_address_types(frame, address.AddressWire):
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
        (qreg := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q0 := py.GetItem(index=idx0.result, obj=qreg.result)),
        (idx1 := as_int(1)),
        (q1 := py.GetItem(index=idx1.result, obj=qreg.result)),
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

    method = build_method(stmts, squin_qubit_with_wire, ilist.IListType)
    frame = run_fold_and_address_analysis(method)

    address_wire_parent_qubit_0 = []
    address_wire_parent_qubit_1 = []
    for address_type in collect_address_types(frame, address.AddressWire):
        if address_type.origin_qubit.data == 0:
            address_wire_parent_qubit_0.append(address_type)
        elif address_type.origin_qubit.data == 1:
            address_wire_parent_qubit_1.append(address_type)

    # Should be 2 AddressWire instances with origin qubit 0
    # and another 2 with origin qubit 1
    assert len(address_wire_parent_qubit_0) == 2
    assert len(address_wire_parent_qubit_1) == 2


def test_tuple():

    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(2)),
        (qreg := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q0 := py.GetItem(index=idx0.result, obj=qreg.result)),
        (idx1 := as_int(1)),
        (q1 := py.GetItem(index=idx1.result, obj=qreg.result)),
        # Unwrap to get wires
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        (w1 := squin.wire.Unwrap(qubit=q1.result)),
        # Put them in an tuple and return to prevent elimination
        (wire_tuple := py.tuple.New((w0.result, w1.result))),
        (func.Return(wire_tuple.result)),
    ]

    method = build_method(
        stmts,
        squin_qubit_with_wire,
        types.Generic(tuple, squin.wire.WireType, squin.wire.WireType),
    )
    frame = run_fold_and_address_analysis(method)

    method.print(analysis=frame.entries)

    address_wires = collect_address_types(frame, address.AddressTuple)
    assert address_wires[0] == address.AddressTuple(
        data=(
            address.AddressWire(origin_qubit=address.AddressQubit(0)),
            address.AddressWire(origin_qubit=address.AddressQubit(1)),
        )
    )


def test_get_item():

    stmts: list[ir.Statement] = [
        # Create qubit register
        (n_qubits := as_int(2)),
        (qreg := squin.qubit.New(n_qubits=n_qubits.result)),
        # Get qubits out
        (idx0 := as_int(0)),
        (q0 := py.GetItem(index=idx0.result, obj=qreg.result)),
        (idx1 := as_int(1)),
        (q1 := py.GetItem(index=idx1.result, obj=qreg.result)),
        # Unwrap to get wires
        (w0 := squin.wire.Unwrap(qubit=q0.result)),
        (w1 := squin.wire.Unwrap(qubit=q1.result)),
        # Put them in a list
        (wire_list := ilist.New([w0.result, w1.result])),
        # create another list just to store the results of the getitems,
        # then return to prevent elimination
        (get_item_idx := as_int(0)),
        (
            get_item_0 := py.GetItem(index=get_item_idx.result, obj=wire_list.result)
        ),  # -> AddressWire
        (func.Return(get_item_0.result)),
    ]

    method = build_method(stmts, squin_qubit_with_wire, squin.wire.WireType)
    frame = run_fold_and_address_analysis(method)

    address_wires = collect_address_types(frame, address.AddressWire)

    assert address_wires[-1] == address.AddressWire(
        origin_qubit=address.AddressQubit(0)
    )


def test_address_wire_is_subset_eq():

    origin_qubit_0 = address.AddressQubit(data=0)
    address_wire_0 = address.AddressWire(origin_qubit=origin_qubit_0)

    origin_qubit_1 = address.AddressQubit(data=1)
    address_wire_1 = address.AddressWire(origin_qubit=origin_qubit_1)

    assert address_wire_0.is_subseteq(address_wire_0)
    assert not address_wire_0.is_subseteq(address_wire_1)

    # fully exercise logic with lattice type that is not address wire
    address_reg = address.AddressReg(data=[0, 1, 2, 3])
    assert not address_wire_0.is_subseteq(address_reg)
