from kirin import ir, types, passes
from bloqade import qasm2, squin
from kirin.ir import dialect_group
from bloqade.types import QubitType
from kirin.prelude import basic

# from kirin.analysis import const
from kirin.dialects import py, func
from bloqade.analysis import address


# ilist.IList()
@dialect_group(basic.add(squin.wire).add(squin.op).add(squin.qubit).add(qasm2.core))
def squin_dialect(self):
    # Const prop analysis runs first, then fold pass takes
    # ConstantFold puts in the type hints! Need that for the
    # get_constant_value method in the address analysis pass
    fold_pass = passes.Fold(self)
    typeinfer_pass = passes.TypeInfer(self)

    def run_pass(
        method: ir.Method,
        *,
        fold: bool = True,
    ):
        method.verify()
        # TODO make special Function rewrite

        if fold:
            fold_pass(method)

        typeinfer_pass(method)
        method.code.typecheck()

    return run_pass


"""
@squin_dialect
def squin_new_qubits():
    # create some new qubits
    qubits = squin.qubit.new(10)
    return qubits
frame, _ = address.AddressAnalysis(squin_new_qubits.dialects).run_analysis(squin_new_qubits)
print(frame)
for ssa_val, addr_type in frame.entries.items():
    print(f"SSA: {ssa_val}\n Addr: {addr_type}")"
"""


# Avoid using frontend, Roger brought up some problems

"""
Desired squin test program,
translate to statements by hand unfortunately
qreg = New(1)
q = q[0]
# Get the wire out
w = unwrap(q)
# Each op will give a new value
v1 = apply(op1, w)
v2 = apply(op2, v1)
v3 = apply(op3, v2)
return v3
"""


def as_int(value: int):
    return py.constant.Constant(value=value)


stmts: list[ir.Statement] = [
    # Create register
    ## I'm going to circumvent the fact that it's not clear to me how to
    ## index into a squin register (or if it's even desirable) and use one from the qasm2.core
    (n_qubits := as_int(2)),
    (qreg := qasm2.core.QRegNew(n_qubits=n_qubits.result)),
    # Get one qubit out
    (idx0 := as_int(0)),
    (q := qasm2.core.QRegGet(reg=qreg.result, idx=idx0.result)),
    (idx1 := as_int(1)),
    (q2 := qasm2.core.QRegGet(reg=qreg.result, idx=idx1.result)),
    # Unwrap to get wire
    (w := squin.wire.Unwrap(qubit=q.result)),
    (w1 := squin.wire.Unwrap(qubit=q2.result)),
    # Use value semantics, keep things simple with operator
    ## Operators are STATEMENTS, you need to
    (op1 := squin.op.stmts.T()),
    (op2 := squin.op.stmts.H()),
    (op3 := squin.op.stmts.X()),
    (v1 := squin.wire.Apply(op1.result, w.result)),
    (v2 := squin.wire.Apply(op2.result, v1.results[0])),
    (v3 := squin.wire.Apply(op3.result, v2.results[0])),
    (op5 := squin.op.stmts.Control(op3.result, n_controls=1)),
    (v45 := squin.wire.Apply(op5.result, v3.results[0], w1.result)),
    # Wrap so the wire goes back "into" the qubit
    # There's no assigned necessary here because Wrap doesn't even
    # return anything
    # (squin.wire.Wrap(wire=v3.results[0], qubit=q.result)),
    (squin.wire.Wrap(wire=v45.results[0], qubit=q.result)),
    (squin.wire.Wrap(wire=v45.results[1], qubit=q2.result)),
    # q0 -> X -> CX
    # q1
    # Can use the qubit with standard qasm2 semantics
    # (qasm2.uop.H(qarg=q.result)),
    (func.Return(q)),
]

block = ir.Block(stmts)  #
block.args.append_from(types.MethodType[[], types.NoneType], "main_self")
func_wrapper = func.Function(
    sym_name="main",
    signature=func.Signature(inputs=(), output=QubitType),
    body=ir.Region(blocks=block),
)

constructed_method = ir.Method(
    mod=None,
    py_func=None,
    sym_name="main",
    dialects=squin_dialect,
    code=func_wrapper,
    arg_names=[],
)

constructed_method.print()

# Now we wrap to get the qubit back
## Can I just reuse the original qubit in the wrapping op?
## -> Yes! That's how it's done in Quake
# squin.wire.wrap(wire=w, qubit=q)

# Need to run the fold pass
# prop = const.Propagate(squin_dialect)
# frame, _ = prop.run_analysis(constructed_method, no_raise=False)
fold_pass = passes.Fold(squin_dialect)
fold_pass(constructed_method)

print("post dead code elimination")
constructed_method.print()

# Run the address analysis and see how things go
frame, _ = address.AddressAnalysis(constructed_method.dialects).run_analysis(
    constructed_method, no_raise=False
)

# If I try plugging in the whole program we run into a missing
# type hint
constructed_method.print(analysis=frame.entries)
# print(frame)
# for ssa_val, addr in frame.entries.items():
#    print(f"SSA Value: {ssa_val}\nAddress Type: {addr}")
