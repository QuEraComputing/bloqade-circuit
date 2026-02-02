from enum import Enum
from typing import Type, final
from dataclasses import dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)
from kirin.dialects.ilist import IList


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


@dataclass
class ConcreteMeasureId(MeasureId):
    """Base class of lattice elements that must be structurally equal to be subseteq."""

    def is_subseteq(self, other: MeasureId) -> bool:
        return self == other


@final
@dataclass
class RawMeasureId(ConcreteMeasureId):
    idx: int


@final
@dataclass
class PhysicalMeasureId(ConcreteMeasureId):
    parent_idx: int
    physical_idx: int


@final
@dataclass
class MeasureIdBool(ConcreteMeasureId):
    idx: int
    predicate: Predicate


@final
@dataclass
class MeasureIdTuple(MeasureId):
    data: tuple[MeasureId, ...]
    obj_type: Type[tuple] | Type[IList]

    def is_subseteq(self, other: MeasureId) -> bool:
        if not (
            isinstance(other, MeasureIdTuple) and len(other.data) == len(self.data)
        ):
            return False

        return all(
            self_elem.is_subseteq(other_elem)
            for self_elem, other_elem in zip(self.data, other.data)
        )

    def join(self, other: MeasureId) -> MeasureId:
        if not (
            isinstance(other, MeasureIdTuple)
            and len(other.data) == len(self.data)
            and other.obj_type is self.obj_type
        ):
            return super().join(other)

        return MeasureIdTuple(
            data=tuple(
                self_elem.join(other_elem)
                for self_elem, other_elem in zip(self.data, other.data)
            ),
            obj_type=self.obj_type,
        )

    def meet(self, other: MeasureId) -> MeasureId:
        if not (
            isinstance(other, MeasureIdTuple)
            and len(other.data) == len(self.data)
            and other.obj_type is self.obj_type
        ):
            return super().meet(other)

        return MeasureIdTuple(
            data=tuple(
                self_elem.meet(other_elem)
                for self_elem, other_elem in zip(self.data, other.data)
            ),
            obj_type=self.obj_type,
        )
