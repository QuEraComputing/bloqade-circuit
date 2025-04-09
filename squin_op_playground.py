from kirin import ir, types
from kirin.passes import Fold
from kirin.dialects import py, func

from bloqade import squin
from bloqade.squin.analysis import shape


def as_int(value: int):
    return py.constant.Constant(value=value)


squin_with_qasm_core = squin.groups.wired.add(py)

stmts: list[ir.Statement] = [
    (h0 := squin.op.stmts.H()),
    (h1 := squin.op.stmts.H()),
    (hh := squin.op.stmts.Kron(lhs=h1.result, rhs=h0.result)),
    (chh := squin.op.stmts.Control(hh.result, n_controls=1)),
    (factor := as_int(1)),
    (schh := squin.op.stmts.Scale(chh.result, factor=factor.result)),
    (func.Return(schh.result)),
]

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
    dialects=squin_with_qasm_core,
    code=func_wrapper,
    arg_names=[],
)

fold_pass = Fold(squin_with_qasm_core)
fold_pass(constructed_method)

""""
address_frame, _ = address.AddressAnalysis(constructed_method.dialects).run_analysis(
    constructed_method, no_raise=False
)


constructed_method.print(analysis=address_frame.entries)
"""

shape_frame, _ = shape.ShapeAnalysis(constructed_method.dialects).run_analysis(
    constructed_method, no_raise=False
)


constructed_method.print(analysis=shape_frame.entries)
