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
class Record(
    SimpleJoinMixin["Record"],
    SimpleMeetMixin["Record"],
    BoundedLattice["Record"],
):

    @classmethod
    def bottom(cls) -> "Record":
        return InvalidRecord()

    @classmethod
    def top(cls) -> "Record":
        return AnyRecord()


# Can pop up if user constructs some list containing a mixture
# of bools from measure results and other places,
# in which case the whole list is invalid
@final
@dataclass
class InvalidRecord(Record, metaclass=SingletonMeta):

    def is_subseteq(self, other: Record) -> bool:
        return True


@final
@dataclass
class AnyRecord(Record, metaclass=SingletonMeta):

    def is_subseteq(self, other: Record) -> bool:
        return isinstance(other, AnyRecord)


@final
@dataclass
class NotRecord(Record, metaclass=SingletonMeta):

    def is_subseteq(self, other: Record) -> bool:
        return isinstance(other, NotRecord)


# For now I only care about propagating constant integers or slices,
# things that can be used as indices to list of measurements
@final
@dataclass
class ConstantCarrier(Record):
    value: int | slice

    def is_subseteq(self, other: Record) -> bool:
        if isinstance(other, ConstantCarrier):
            return self.value == other.value
        return False


@final
@dataclass
class RecordIdx(Record):
    idx: int
    id: int

    def is_subseteq(self, other: Record) -> bool:
        if isinstance(other, RecordIdx):
            return self.idx == other.idx
        return False


@final
@dataclass
class RecordTuple(Record):
    members: tuple[RecordIdx, ...]

    def is_subseteq(self, other: Record) -> bool:
        if isinstance(other, RecordTuple):
            return all(a.is_subseteq(b) for a, b in zip(self.members, other.members))
        return False


@final
@dataclass
class ImmutableRecords(Record):
    members: tuple[RecordIdx, ...]

    def is_subseteq(self, other: Record) -> bool:
        if isinstance(other, ImmutableRecords):
            return all(a.is_subseteq(b) for a, b in zip(self.members, other.members))
        return False
