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


OpType = types.PyClass(Op)
MultiQubitPauliOpType = types.PyClass(MultiQubitPauliOp)
PauliStringType = types.PyClass(PauliStringOp)
PauliOpType = types.PyClass(PauliOp)

NumOperators = types.TypeVar("NumOperators")
