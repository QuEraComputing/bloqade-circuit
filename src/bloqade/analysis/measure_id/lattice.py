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


@dataclass
class ConcreteMeasureId(MeasureId):
    """Base class of lattice elements that must be structurally equal to be subseteq."""

    def is_subseteq(self, other: MeasureId) -> bool:
        return self == other


@final
@dataclass
class RawMeasureId(ConcreteMeasureId):
    idx: int
    predicate: Predicate | None = None


@final
@dataclass
class DetectorId(MeasureId):
    idx: int
    data: MeasureId

    def is_subseteq(self, other: MeasureId) -> bool:
        return (
            isinstance(other, DetectorId)
            and self.idx == other.idx
            and self.data.is_subseteq(other.data)
        )


@final
@dataclass
class ObservableId(MeasureId):
    idx: int
    data: MeasureId

    def is_subseteq(self, other: MeasureId) -> bool:
        return (
            isinstance(other, ObservableId)
            and self.idx == other.idx
            and self.data.is_subseteq(other.data)
        )


@final
@dataclass
class MeasureIdTuple(MeasureId):
    data: tuple[MeasureId, ...]
    obj_type: Type[tuple] | Type[IList] = IList
    predicate: Predicate | None = None

    def is_subseteq(self, other: MeasureId) -> bool:
        if not (
            isinstance(other, MeasureIdTuple) and len(other.data) == len(self.data)
        ):
            return False

        return self.predicate == other.predicate and all(
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
            predicate=self.predicate if self.predicate == other.predicate else None,
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
            predicate=self.predicate if self.predicate == other.predicate else None,
        )


@final
@dataclass
class ConstantCarrier(MeasureId):
    value: int | slice

    def is_subseteq(self, other: MeasureId) -> bool:
        if isinstance(other, ConstantCarrier):
            return self.value == other.value
        return False
