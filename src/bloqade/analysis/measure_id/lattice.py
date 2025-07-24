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


# Can pop up if user constructs some list containing a mixture
# of bools from measure results and other places,
# in which case the whole list is invalid
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
class MeasureIdBool(MeasureId):
    idx: int

    def is_subseteq(self, other: MeasureId) -> bool:
        if isinstance(other, MeasureIdBool):
            return self.idx == other.idx
        return False


# Might be nice to have some print override
# here so all the CanMeasureId's/other types are consolidated for
# readability


@final
@dataclass
class MeasureIdTuple(MeasureId):
    data: tuple[MeasureId, ...]

    def is_subseteq(self, other: MeasureId) -> bool:
        if isinstance(other, MeasureIdTuple):
            return all(a.is_subseteq(b) for a, b in zip(self.data, other.data))
        return False
