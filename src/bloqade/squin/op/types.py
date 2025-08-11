from typing import Generic, TypeVar, overload

from kirin import types


class Op:

    def __matmul__(self, other: "Op") -> "Op":
        raise NotImplementedError("@ can only be used within a squin kernel program")

    @overload
    def __mul__(self, other: "Op") -> "Op": ...

    @overload
    def __mul__(self, other: complex) -> "Op": ...

    def __mul__(self, other) -> "Op":
        raise NotImplementedError("@ can only be used within a squin kernel program")

    def __rmul__(self, other: complex) -> "Op":
        raise NotImplementedError("@ can only be used within a squin kernel program")


OpType = types.PyClass(Op)


class CompositeOp(Op):
    pass


CompositeOpType = types.PyClass(CompositeOp)


class BinaryOp(Op):
    pass


BinaryOpType = types.PyClass(BinaryOp)

LhsType = TypeVar("LhsType", bound=Op)
RhsType = TypeVar("RhsType", bound=Op)


class Mult(BinaryOp, Generic[LhsType, RhsType]):
    lhs: LhsType
    rhs: RhsType


MultType = types.Generic(Mult, OpType, OpType)


class MultiQubitPauliOp(Op):
    pass


MultiQubitPauliOpType = types.PyClass(MultiQubitPauliOp)


class PauliStringOp(MultiQubitPauliOp):
    pass


PauliStringType = types.PyClass(PauliStringOp)


class PauliOp(MultiQubitPauliOp):
    pass


PauliOpType = types.PyClass(PauliOp)


class XOp(PauliOp):
    pass


XOpType = types.PyClass(XOp)


class YOp(PauliOp):
    pass


YOpType = types.PyClass(YOp)


class ZOp(PauliOp):
    pass


ZOpType = types.PyClass(ZOp)


ControlledOp = TypeVar("ControlledOp", bound=Op)


class ControlOp(CompositeOp, Generic[ControlledOp]):
    op: ControlledOp


ControlledOpType = types.TypeVar("ControlledOp", bound=OpType)
ControlOpType = types.Generic(ControlOp, ControlledOpType)
CXOpType = types.Generic(ControlOp, XOpType)
CYOpType = types.Generic(ControlOp, YOpType)
CZOpType = types.Generic(ControlOp, ZOpType)

RotationAxis = TypeVar("RotationAxis", bound=Op)


class ROp(CompositeOp, Generic[RotationAxis]):
    axis: RotationAxis
    angle: float


ROpType = types.Generic(ROp, OpType)
RxOpType = types.Generic(ROp, XOpType)
RyOpType = types.Generic(ROp, YOpType)
RzOpType = types.Generic(ROp, ZOpType)


NumOperators = types.TypeVar("NumOperators", bound=types.Int)
