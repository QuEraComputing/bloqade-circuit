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

    # Should be using the Sized trait
    # that the statements have
    pass
