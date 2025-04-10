from typing import final
from dataclasses import dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)


@dataclass
class Sites(
    SimpleJoinMixin["Sites"], SimpleMeetMixin["Sites"], BoundedLattice["Sites"]
):
    @classmethod
    def bottom(cls) -> "Sites":
        return NoSites()

    @classmethod
    def top(cls) -> "Sites":
        return AnySites()


@final
@dataclass
class NoSites(Sites, metaclass=SingletonMeta):

    def is_subseteq(self, other: Sites) -> bool:
        return True


@final
@dataclass
class AnySites(Sites, metaclass=SingletonMeta):

    def is_subseteq(self, other: Sites) -> bool:
        return isinstance(other, Sites)


@final
@dataclass
class NumberSites(Sites):
    sites: int

    def is_subseteq(self, other: Sites) -> bool:
        if isinstance(other, NumberSites):
            return self.sites == other.sites
        return False
