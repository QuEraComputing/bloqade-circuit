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


class ControlOp(Op, Generic[ControlledOp]):
    pass


ControlledOpType = types.TypeVar("ControlledOp", bound=OpType)
ControlOpType = types.Generic(ControlOp, ControlledOpType)
CXOpType = types.Generic(ControlOp, XOpType)
CYOpType = types.Generic(ControlOp, YOpType)
CZOpType = types.Generic(ControlOp, ZOpType)

RotationAxis = TypeVar("RotationAxis", bound=Op)
RotationAngle = TypeVar("RotationAngle", bound=float)


class ROp(Op, Generic[RotationAxis, RotationAngle]):
    axis_angle: Op
    rotation_angle: RotationAngle


RotationAxisType = types.TypeVar("RotationAxis", bound=OpType)
RotationAngleType = types.TypeVar("RotationAngle", bound=types.Float)
ROpType = types.Generic(ROp, RotationAxisType, RotationAngleType)
RxOpType = types.Generic(ROp, XOpType, RotationAngleType)
RyOpType = types.Generic(ROp, YOpType, RotationAngleType)
RzOpType = types.Generic(ROp, ZOpType, RotationAngleType)


NumOperators = types.TypeVar("NumOperators", bound=types.Int)
