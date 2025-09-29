import typing

from kirin import lowering
from kirin.dialects import ilist

from bloqade.squin import qubit

from .stmts import CZ, R, Rz

Len = typing.TypeVar("Len")


@lowering.wraps(CZ)
def cz(
    controls: ilist.IList[qubit.Qubit, Len],
    targets: ilist.IList[qubit.Qubit, Len],
): ...


@lowering.wraps(R)
def r(
    qubits: ilist.IList[qubit.Qubit, typing.Any],
    axis_angle: float,
    rotation_angle: float,
): ...


@lowering.wraps(Rz)
def rz(
    qubits: ilist.IList[qubit.Qubit, typing.Any],
    rotation_angle: float,
): ...
