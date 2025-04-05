from typing import Union, Sequence, final
from dataclasses import dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)


@dataclass
class Address(
    SimpleJoinMixin["Address"],
    SimpleMeetMixin["Address"],
    BoundedLattice["Address"],
):

    @classmethod
    def bottom(cls) -> "Address":
        return NotQubit()

    @classmethod
    def top(cls) -> "Address":
        return AnyAddress()


@final
@dataclass
class NotQubit(Address, metaclass=SingletonMeta):

    def is_subseteq(self, other: Address) -> bool:
        return True


@final
@dataclass
class AnyAddress(Address, metaclass=SingletonMeta):

    def is_subseteq(self, other: Address) -> bool:
        return isinstance(other, AnyAddress)


@final
@dataclass
class AddressTuple(Address):
    data: tuple[Address, ...]

    def is_subseteq(self, other: Address) -> bool:
        if isinstance(other, AddressTuple):
            return all(a.is_subseteq(b) for a, b in zip(self.data, other.data))
        return False


@final
@dataclass
class AddressReg(Address):
    data: Sequence[int]

    def is_subseteq(self, other: Address) -> bool:
        if isinstance(other, AddressReg):
            return self.data == other.data
        return False


@final
@dataclass
class AddressQubit(Address):
    data: int

    def is_subseteq(self, other: Address) -> bool:
        if isinstance(other, AddressQubit):
            return self.data == other.data
        return False


@final
@dataclass
class AddressWire(Address):
    parent: Union[AddressQubit, "AddressWire"]
    # Should have a 1 - 1 correspondence with the actual qubit being tracked
    # I imagine I could actually just plug in another address type?
    # It would HAVE to be an existing QubitAddress

    def is_subseteq(self, other: Address) -> bool:
        if isinstance(other, AddressWire):
            return self.parent == self.parent
        return False


"""
AddressQubit -> AddressWire -> AddressWire
"""
