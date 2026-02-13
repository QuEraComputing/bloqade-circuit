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


@dataclass(eq=False)
class MutableIdx:
    """Mutable wrapper for integer index, enabling shared references."""

    value: int

    def __repr__(self) -> str:
        return f"MutableIdx({self.value})"

    def __hash__(self) -> int:
        return id(self)


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
    _idx: MutableIdx
    predicate: Predicate | None = None

    def __init__(self, idx: int | MutableIdx, predicate: Predicate | None = None):
        if isinstance(idx, int):
            self._idx = MutableIdx(idx)
        else:
            self._idx = idx
        self.predicate = predicate

    @property
    def idx(self) -> int:
        return self._idx.value

    @idx.setter
    def idx(self, value: int) -> None:
        self._idx.value = value

    @property
    def mutable_idx(self) -> MutableIdx:
        """Access the underlying MutableIdx (for buffer operations)."""
        return self._idx

    def with_predicate(self, predicate: Predicate) -> "RawMeasureId":
        """Create a predicated copy sharing the same MutableIdx."""
        return RawMeasureId(self._idx, predicate)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RawMeasureId):
            return False
        return self.idx == other.idx and self.predicate == other.predicate

    def __repr__(self) -> str:
        if self.predicate is not None:
            return f"({self.idx}, {self.predicate})"
        return str(self.idx)

    def __hash__(self) -> int:
        return hash((self.idx, self.predicate))


@final
@dataclass
class DetectorId(MeasureId):
    idx: int
    data: MeasureId
    coordinates: tuple[int | float, ...]

    def is_subseteq(self, other: MeasureId) -> bool:
        return (
            isinstance(other, DetectorId)
            and self.idx == other.idx
            and self.data.is_subseteq(other.data)
            and self.coordinates == other.coordinates
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

    def __repr__(self) -> str:
        parts = []
        for elem in self.data:
            if isinstance(elem, RawMeasureId):
                if elem.predicate is not None:
                    parts.append(f"({elem.idx}, {elem.predicate})")
                else:
                    parts.append(str(elem.idx))
            else:
                parts.append(repr(elem))
        return f"({', '.join(parts)})"

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


@final
@dataclass
class ConstantCarrier(MeasureId):
    value: int | float | slice

    def __repr__(self) -> str:
        return f"ConstantCarrier({self.value})"

    def is_subseteq(self, other: MeasureId) -> bool:
        if isinstance(other, ConstantCarrier):
            return self.value == other.value
        return False
