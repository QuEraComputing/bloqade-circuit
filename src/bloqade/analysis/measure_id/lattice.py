from enum import Enum
from typing import final
from dataclasses import dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)


class Predicate(Enum):
    IS_ZERO = 1
    IS_ONE = 2
    IS_LOST = 3

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name


# Taken directly from Kai-Hsin Wu's implementation
# with minor changes to names


@dataclass
class MeasureId(
    SimpleJoinMixin["MeasureId"],
    SimpleMeetMixin["MeasureId"],
    BoundedLattice["MeasureId"],
):

    @classmethod
    def bottom(cls) -> "MeasureId":
        return InvalidMeasureId()

    @classmethod
    def top(cls) -> "MeasureId":
        return AnyMeasureId()


@final
@dataclass
class InvalidMeasureId(MeasureId, metaclass=SingletonMeta):

    def is_subseteq(self, other: MeasureId) -> bool:
        return True


@final
@dataclass
class AnyMeasureId(MeasureId, metaclass=SingletonMeta):

    def is_subseteq(self, other: MeasureId) -> bool:
        return isinstance(other, AnyMeasureId)


@final
@dataclass
class NotMeasureId(MeasureId, metaclass=SingletonMeta):

    def is_subseteq(self, other: MeasureId) -> bool:
        return isinstance(other, NotMeasureId)


@final
@dataclass
class RawMeasureId(MeasureId):
    idx: int

    def is_subseteq(self, other: MeasureId) -> bool:
        if isinstance(other, RawMeasureId):
            return self.idx == other.idx
        return False


@final
@dataclass
class MeasureIdTuple(MeasureId):
    data: tuple[RawMeasureId, ...]
    immutable: bool = False

    def is_subseteq(self, other: MeasureId) -> bool:
        if isinstance(other, MeasureIdTuple):
            return all(a.is_subseteq(b) for a, b in zip(self.data, other.data))
        return False


@final
@dataclass
class PredicatedMeasureId(MeasureId):
    on_type: MeasureIdTuple | RawMeasureId
    cond: Predicate

    def is_subseteq(self, other: MeasureId) -> bool:
        if isinstance(other, PredicatedMeasureId):
            return self.cond == other.cond and self.on_type.is_subseteq(other.on_type)
        return False


# For now I only care about propagating constant integers or slices,
# things that can be used as indices to list of measurements
@final
@dataclass
class ConstantCarrier(MeasureId):
    value: int | slice

    def is_subseteq(self, other: MeasureId) -> bool:
        if isinstance(other, ConstantCarrier):
            return self.value == other.value
        return False
