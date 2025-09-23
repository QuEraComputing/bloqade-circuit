from typing import Any, TypeVar

from kirin.dialects import ilist
from kirin.lowering import wraps

from bloqade.types import Qubit

from .stmts import (
    CX,
    CY,
    CZ,
    H,
    S,
    T,
    X,
    Y,
    Z,
    Rx,
    Ry,
    Rz,
    Sqrt_X,
    Sqrt_Y,
)


@wraps(X)
def x(qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None: ...


@wraps(Y)
def y(qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None: ...


@wraps(Z)
def z(qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None: ...


@wraps(H)
def h(qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None: ...


@wraps(T)
def t(qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None: ...


@wraps(S)
def s(qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None: ...


@wraps(Sqrt_X)
def sqrt_x(qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None: ...


@wraps(Sqrt_Y)
def sqrt_y(qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None: ...


@wraps(Rx)
def rx(angle: float, qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None: ...


@wraps(Ry)
def ry(angle: float, qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None: ...


@wraps(Rz)
def rz(angle: float, qubits: ilist.IList[Qubit, Any] | list[Qubit]) -> None: ...


Len = TypeVar("Len", bound=int)


@wraps(CX)
def cx(
    controls: ilist.IList[Qubit, Len] | list[Qubit],
    targets: ilist.IList[Qubit, Len] | list[Qubit],
) -> None: ...


@wraps(CY)
def cy(
    controls: ilist.IList[Qubit, Len] | list[Qubit],
    targets: ilist.IList[Qubit, Len] | list[Qubit],
) -> None: ...


@wraps(CZ)
def cz(
    controls: ilist.IList[Qubit, Len] | list[Qubit],
    targets: ilist.IList[Qubit, Len] | list[Qubit],
) -> None: ...
