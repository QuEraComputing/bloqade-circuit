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
class HermitianLattice(
    SimpleJoinMixin["HermitianLattice"],
    SimpleMeetMixin["HermitianLattice"],
    IsSubsetEqMixin["HermitianLattice"],
    BoundedLattice["HermitianLattice"],
):
    @classmethod
    def bottom(cls) -> "HermitianLattice":
        return NotAnOperator()

    @classmethod
    def top(cls) -> "HermitianLattice":
        return NotHermitian()


@final
@dataclass
class NotAnOperator(HermitianLattice, metaclass=SingletonMeta):
    pass


@final
@dataclass
class NotHermitian(HermitianLattice, metaclass=SingletonMeta):
    pass


@final
@dataclass
class Hermitian(HermitianLattice, metaclass=SingletonMeta):
    def is_subseteq(self, other: HermitianLattice) -> bool:
        return isinstance(other, Hermitian)
