from typing import final
from dataclasses import dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)


@dataclass
class UnitaryLattice(
    SimpleJoinMixin["UnitaryLattice"],
    SimpleMeetMixin["UnitaryLattice"],
    BoundedLattice["UnitaryLattice"],
):
    @classmethod
    def bottom(cls) -> "UnitaryLattice":
        return NotAnOperator()

    @classmethod
    def top(cls) -> "UnitaryLattice":
        return NotUnitary()


@final
@dataclass
class NotAnOperator(UnitaryLattice, metaclass=SingletonMeta):

    def is_subseteq(self, other: UnitaryLattice) -> bool:
        return True


@final
@dataclass
class NotUnitary(UnitaryLattice, metaclass=SingletonMeta):

    def is_subseteq(self, other: UnitaryLattice) -> bool:
        return True


@final
@dataclass
class Unitary(UnitaryLattice, metaclass=SingletonMeta):

    def is_subseteq(self, other: UnitaryLattice) -> bool:
        return True
