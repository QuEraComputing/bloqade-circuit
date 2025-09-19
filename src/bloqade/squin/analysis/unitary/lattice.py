from typing import final
from dataclasses import dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    IsSubsetEqMixin,
    SimpleJoinMixin,
    SimpleMeetMixin,
)


@dataclass
class UnitaryLattice(
    SimpleJoinMixin["UnitaryLattice"],
    SimpleMeetMixin["UnitaryLattice"],
    IsSubsetEqMixin["UnitaryLattice"],
    BoundedLattice["UnitaryLattice"],
):
    @classmethod
    def bottom(cls) -> "UnitaryLattice":
        return NotAnOperator()

    @classmethod
    def top(cls) -> "UnitaryLattice":
        return PossiblyUnitary()


@final
@dataclass
class NotAnOperator(UnitaryLattice, metaclass=SingletonMeta):
    pass


@final
@dataclass
class NotUnitary(UnitaryLattice, metaclass=SingletonMeta):

    def is_subseteq(self, other: UnitaryLattice) -> bool:
        return isinstance(other, NotUnitary)


@final
@dataclass
class Unitary(UnitaryLattice, metaclass=SingletonMeta):

    def is_subseteq(self, other: UnitaryLattice) -> bool:
        return isinstance(other, Unitary)


@final
@dataclass
class PossiblyUnitary(UnitaryLattice, metaclass=SingletonMeta):
    pass
