from kirin import ir, types
from kirin.passes import Fold
from kirin.dialects import py, func, ilist

from bloqade import qasm2, squin
from bloqade.analysis import address
from bloqade.squin.analysis import shape


def as_int(value: int):
    return py.constant.Constant(value=value)


squin_with_qasm_core = squin.groups.wired.add(qasm2.core).add(ilist)

stmts: list[ir.Statement] = [
    # Create qubit register
    (n_qubits := as_int(1)),
    (qreg := qasm2.core.QRegNew(n_qubits=n_qubits.result)),
    # Get qubits out
    (idx0 := as_int(0)),
    (q0 := qasm2.core.QRegGet(reg=qreg.result, idx=idx0.result)),
    # Unwrap to get wires
    (w1 := squin.wire.Unwrap(qubit=q0.result)),
    # Pass wire into operator
    (op := squin.op.stmts.H()),
    (v1 := squin.wire.Apply(op.result, w1.result)),
    # Test Identity
    (id := squin.op.stmts.Identity(size=1)),
    (v2 := squin.wire.Apply(id.result, v1.results[0])),
    # Keep Passing Operators
    (func.Return(v2.results[0])),
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

frame, _ = shape.ShapeAnalysis(constructed_method.dialects).run_analysis(
    constructed_method, no_raise=False
)

"""
frame, _ = address.AddressAnalysis(constructed_method.dialects).run_analysis(
    constructed_method, no_raise=False
"""

constructed_method.print(analysis=frame.entries)
