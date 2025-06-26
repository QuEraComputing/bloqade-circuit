import math

from kirin import ir, types
from kirin.rewrite import Walk, Chain
from kirin.dialects import func
from kirin.rewrite.dce import DeadCodeElimination

from bloqade.squin import op, wire, qubit, kernel
from bloqade.squin.rewrite.U3_to_clifford import SquinU3ToClifford


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


def test_x():

    @kernel
    def main_x():
        q = qubit.new(4)
        oper = op.u(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.5 * math.tau)
        qubit.apply(oper, q[0])

    main_x.print()
    Walk(Chain(Walk(SquinU3ToClifford()), Walk(DeadCodeElimination()))).rewrite(
        main_x.code
    )
    main_x.print()


def test_s():

    @kernel
    def main_s():
        q = qubit.new(4)
        oper = op.u(theta=0.0 * math.tau, phi=0.0 * math.tau, lam=-0.25 * math.tau)
        qubit.apply(oper, q[0])

    main_s.print()
    Walk(Chain(Walk(SquinU3ToClifford()), Walk(DeadCodeElimination()))).rewrite(
        main_s.code
    )
    main_s.print()


test_s()
