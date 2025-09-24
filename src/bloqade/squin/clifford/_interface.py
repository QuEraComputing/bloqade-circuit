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
    SqrtX,
    SqrtY,
)


@wraps(X)
def x(qubits: ilist.IList[Qubit, Any]) -> None: ...


@wraps(Y)
def y(qubits: ilist.IList[Qubit, Any]) -> None: ...


@wraps(Z)
def z(qubits: ilist.IList[Qubit, Any]) -> None: ...


@wraps(H)
def h(qubits: ilist.IList[Qubit, Any]) -> None: ...


@wraps(T)
def t(qubits: ilist.IList[Qubit, Any], *, adjoint: bool) -> None: ...


@wraps(S)
def s(qubits: ilist.IList[Qubit, Any], *, adjoint: bool) -> None: ...


@wraps(SqrtX)
def sqrt_x(qubits: ilist.IList[Qubit, Any], *, adjoint: bool) -> None: ...


@wraps(SqrtY)
def sqrt_y(qubits: ilist.IList[Qubit, Any], *, adjoint: bool) -> None: ...


@wraps(Rx)
def rx(angle: float, qubits: ilist.IList[Qubit, Any]) -> None: ...


@wraps(Ry)
def ry(angle: float, qubits: ilist.IList[Qubit, Any]) -> None: ...


@wraps(Rz)
def rz(angle: float, qubits: ilist.IList[Qubit, Any]) -> None: ...


Len = TypeVar("Len", bound=int)


@wraps(CX)
def cx(
    controls: ilist.IList[Qubit, Len],
    targets: ilist.IList[Qubit, Len],
) -> None: ...


@wraps(CY)
def cy(
    controls: ilist.IList[Qubit, Len],
    targets: ilist.IList[Qubit, Len],
) -> None: ...


@wraps(CZ)
def cz(
    controls: ilist.IList[Qubit, Len],
    targets: ilist.IList[Qubit, Len],
) -> None: ...
