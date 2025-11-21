from typing import final
from dataclasses import dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)

# Taken directly from Kai-Hsin Wu's implementation
# with minor changes to names and addition of CanMeasureId type


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
class KnownMeasureId(MeasureId):
    idx: int

    def is_subseteq(self, other: MeasureId) -> bool:
        if isinstance(other, KnownMeasureId):
            return self.idx == other.idx
        return False


@final
@dataclass
class MeasureIdTuple(MeasureId):
    data: tuple[MeasureId, ...]

    def is_subseteq(self, other: MeasureId) -> bool:
        if isinstance(other, MeasureIdTuple):
            return all(a.is_subseteq(b) for a, b in zip(self.data, other.data))
        return False


@final
@dataclass
class ImmutableMeasureIds(MeasureId):
    data: tuple[KnownMeasureId, ...]

    def is_subseteq(self, other: MeasureId) -> bool:
        if isinstance(other, ImmutableMeasureIds):
            return all(a.is_subseteq(b) for a, b in zip(self.data, other.data))
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
