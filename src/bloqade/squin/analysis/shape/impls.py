from typing import cast

from kirin import ir, interp

from bloqade.squin import op

from .lattice import (
    NoShape,
    OpShape,
)
from .analysis import ShapeAnalysis


@op.dialect.register(key="op.shape")
class SquinOp(interp.MethodTable):

    @interp.impl(op.stmts.Kron)
    def kron(self, interp: ShapeAnalysis, frame: interp.Frame, stmt: op.stmts.Kron):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        if isinstance(lhs, OpShape) and isinstance(rhs, OpShape):
            new_size = lhs.size + rhs.size
            return (OpShape(size=new_size),)
        else:
            return (NoShape(),)

    @interp.impl(op.stmts.Mult)
    def mult(self, interp: ShapeAnalysis, frame: interp.Frame, stmt: op.stmts.Mult):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)

        if isinstance(lhs, OpShape) and isinstance(rhs, OpShape):
            lhs_size = lhs.size
            rhs_size = rhs.size
            # Sized trait implicitly enforces that
            # all operators are square matrices,
            # not sure if it's worth raising an exception here
            # or just letting this propagate...
            if lhs_size != rhs_size:
                return (NoShape(),)
            else:
                return (OpShape(size=lhs_size + rhs_size),)
        else:
            return (NoShape(),)

    @interp.impl(op.stmts.Control)
    def control(
        self, interp: ShapeAnalysis, frame: interp.Frame, stmt: op.stmts.Control
    ):
        op_shape = frame.get(stmt.op)

        if isinstance(op_shape, OpShape):
            op_size = op_shape.size
            n_controls_attr = stmt.get_attr_or_prop("n_controls")
            n_controls = cast(ir.PyAttr[int], n_controls_attr).data
            return (OpShape(size=op_size + n_controls),)
        else:
            return (NoShape(),)

    @interp.impl(op.stmts.Rot)
    def rot(self, interp: ShapeAnalysis, frame: interp.Frame, stmt: op.stmts.Rot):
        op_shape = frame.get(stmt.axis)
        return (op_shape,)

    @interp.impl(op.stmts.Scale)
    def scale(self, interp: ShapeAnalysis, frame: interp.Frame, stmt: op.stmts.Scale):
        op_shape = frame.get(stmt.op)
        return (op_shape,)
