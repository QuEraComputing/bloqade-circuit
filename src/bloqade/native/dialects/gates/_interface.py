import typing

from kirin import lowering
from kirin.dialects import ilist

from bloqade.squin import qubit

from .stmts import CZ, R, Rz

Len = typing.TypeVar("Len")


@lowering.wraps(CZ)
def cz(
    ctrls: ilist.IList[qubit.Qubit, Len],
    qargs: ilist.IList[qubit.Qubit, Len],
): ...


@lowering.wraps(R)
def r(
    inputs: ilist.IList[qubit.Qubit, typing.Any],
    axis_angle: float,
    rotation_angle: float,
): ...


@lowering.wraps(Rz)
def rz(
    inputs: ilist.IList[qubit.Qubit, typing.Any],
    rotation_angle: float,
): ...
