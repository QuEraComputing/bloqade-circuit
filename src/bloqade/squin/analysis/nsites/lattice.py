from typing import final
from dataclasses import dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)


@dataclass
class NSites(
    SimpleJoinMixin["NSites"], SimpleMeetMixin["NSites"], BoundedLattice["NSites"]
):
    @classmethod
    def bottom(cls) -> "NSites":
        return NoSites()

    @classmethod
    def top(cls) -> "NSites":
        return AnySites()


@final
@dataclass
class NoSites(NSites, metaclass=SingletonMeta):

    def is_subseteq(self, other: NSites) -> bool:
        return True


@final
@dataclass
class AnySites(NSites, metaclass=SingletonMeta):

    def is_subseteq(self, other: NSites) -> bool:
        return isinstance(other, NSites)


@final
@dataclass
class HasNSites(NSites):
    sites: int

    def is_subseteq(self, other: NSites) -> bool:
        if isinstance(other, HasNSites):
            return self.sites == other.sites
        return False
