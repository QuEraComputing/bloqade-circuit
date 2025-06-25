import math

from kirin import ir, types
from kirin.rewrite import Walk, Chain
from kirin.dialects import func
from kirin.rewrite.dce import DeadCodeElimination

from bloqade.squin import op, wire, kernel
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
        return op.stmts.U3(theta=0.5 * math.tau, phi=0.0 * math.tau, lam=0.5 * math.tau)

    main_x.print()
    Chain(Walk(SquinU3ToClifford()), Walk(DeadCodeElimination())).rewrite(main_x.code)
    main_x.print()

    assert isinstance(main_x.callable_region.blocks[0].stmts.at(0), op.stmts.X)
