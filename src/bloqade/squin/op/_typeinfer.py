import math

from kirin import types, interp
from kirin.analysis import ForwardFrame, typeinfer

from . import stmts, types as op_types
from ._dialect import dialect


@dialect.register(key="typeinfer")
class TypeInferOperators(interp.MethodTable):

    @interp.impl(stmts.X)
    def x(
        self,
        _interp: typeinfer.TypeInference,
        frame: ForwardFrame[types.TypeAttribute],
        stmt: stmts.X,
    ):
        return (op_types.PauliXOpType,)

    @interp.impl(stmts.Y)
    def y(
        self,
        _interp: typeinfer.TypeInference,
        frame: ForwardFrame[types.TypeAttribute],
        stmt: stmts.Y,
    ):
        return (op_types.PauliYOpType,)

    @interp.impl(stmts.Z)
    def z(
        self,
        _interp: typeinfer.TypeInference,
        frame: ForwardFrame[types.TypeAttribute],
        stmt: stmts.Z,
    ):
        return (op_types.PauliZOpType,)

    @interp.impl(stmts.Control)
    def control(
        self,
        _interp: typeinfer.TypeInference,
        frame: ForwardFrame[types.TypeAttribute],
        stmt: stmts.Control,
    ):
        operator = frame.get(stmt.op)
        if operator.is_subset(op_types.PauliZOpType):
            return (op_types.CZOpType,)

        return (op_types.OpType,)

    @interp.impl(stmts.Rot)
    def rot(
        self,
        _interp: typeinfer.TypeInference,
        frame: ForwardFrame[types.TypeAttribute],
        stmt: stmts.Rot,
    ):
        angle = frame.get(stmt.angle)
        axis = frame.get(stmt.axis)

        if axis.is_subseteq(op_types.PauliZOpType):
            return (op_types.RzOpType[angle],)
        elif axis.is_subseteq(op_types.PauliXOpType):
            axis_angle = types.Literal(0.0)
            return (op_types.RxyOpType[axis_angle, angle],)
        elif axis.is_subseteq(op_types.PauliYOpType):
            axis_angle = types.Literal(math.pi / 2)
            return (op_types.RxyOpType[axis_angle, angle],)
        else:
            return (op_types.OpType,)
