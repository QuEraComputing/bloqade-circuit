from kirin import interp

from bloqade import squin

""" from .lattice import (
    Shape,
    NoShape,
    OpShape,
)

from .analysis import ShapeAnalysis """


@squin.op.dialect.register(key="op.shape")
class SquinOp(interp.MethodTable):
    pass

    # Should be using the Sized trait
    # that the statements have

    # Need to keep in mind that Identity
    # has a HasSize() trait with "size:int"
    # as the corresponding attribute to query
    # @interp.impl(squin.op.stmts.ConstantUnitary)
