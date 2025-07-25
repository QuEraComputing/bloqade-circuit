from typing import overload

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


class MultiQubitPauliOp(Op):
    pass


class PauliStringOp(MultiQubitPauliOp):
    pass


class PauliOp(MultiQubitPauliOp):
    pass


class NativeOp(Op):
    pass


class CZOp(NativeOp):
    pass


class RzOp(NativeOp):
    pass


class RxyOp(NativeOp):
    pass


class PauliXOp(PauliOp, NativeOp):
    pass


class PauliYOp(PauliOp, NativeOp):
    pass


class PauliZOp(PauliOp, NativeOp):
    pass


OpType = types.PyClass(Op)
MultiQubitPauliOpType = types.PyClass(MultiQubitPauliOp)
PauliStringType = types.PyClass(PauliStringOp)
PauliOpType = types.PyClass(PauliOp)
NativeOpType = types.PyClass(NativeOp)
CZOpType = types.PyClass(CZOp)
RzOpType = types.Generic(RzOp, types.TypeVar("rotation_angle", bound=types.Float))
RxyOpType = types.Generic(
    RxyOp,
    types.TypeVar("axis_angle", bound=types.Float),
    types.TypeVar("rotation_angle", bound=types.Float),
)
PauliXOpType = types.PyClass(PauliXOp)
PauliYOpType = types.PyClass(PauliYOp)
PauliZOpType = types.PyClass(PauliZOp)

NumOperators = types.TypeVar("NumOperators")
