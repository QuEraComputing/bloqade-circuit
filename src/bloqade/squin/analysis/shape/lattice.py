from typing import final
from dataclasses import dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)


@dataclass
class Shape(
    SimpleJoinMixin["Shape"], SimpleMeetMixin["Shape"], BoundedLattice["Shape"]
):
    @classmethod
    def bottom(cls) -> "Shape":
        return NoShape()

    @classmethod
    def top(cls) -> "Shape":
        return AnyShape()


@final
@dataclass
class NoShape(Shape, metaclass=SingletonMeta):

    def is_subseteq(self, other: Shape) -> bool:
        return True


@final
@dataclass
class AnyShape(Shape, metaclass=SingletonMeta):

    def is_subseteq(self, other: Shape) -> bool:
        return isinstance(other, Shape)


@final
@dataclass
class OpShape(Shape):
    size: int

    def is_subseteq(self, other: Shape) -> bool:
        if isinstance(other, OpShape):
            return self.size == other.size
        return False
