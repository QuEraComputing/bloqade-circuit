import typing

from kirin import lowering
from kirin.dialects import ilist

from bloqade import qubit

from .stmts import CZ, R, Rz

Len = typing.TypeVar("Len")


@lowering.wraps(CZ)
def cz(
    controls: ilist.IList[qubit.Qubit, Len],
    targets: ilist.IList[qubit.Qubit, Len],
): ...


@lowering.wraps(R)
def r(
    axis_angle: float,
    rotation_angle: float,
    qubits: ilist.IList[qubit.Qubit, typing.Any],
): ...


@lowering.wraps(Rz)
def rz(
    rotation_angle: float,
    qubits: ilist.IList[qubit.Qubit, typing.Any],
): ...
