from typing import final
from dataclasses import field, dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)
from kirin.analysis import const


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
class AddressQubit(Address):
    data: int

    def is_subseteq(self, other: Address) -> bool:
        if isinstance(other, AddressQubit):
            return self.data == other.data
        return False


@final
@dataclass
class AddressWire(Address):
    origin_qubit: AddressQubit

    def is_subseteq(self, other: Address) -> bool:
        if isinstance(other, AddressWire):
            return self.origin_qubit == other.origin_qubit
        return False


@dataclass
class JointLattice(BoundedLattice):
    address: Address = field(default_factory=Address.top)
    constant: const.Result = field(default_factory=const.Result.top)

    def __post_init__(self):
        assert isinstance(self.address, Address)
        assert isinstance(self.constant, const.Result)

    @classmethod
    def bottom(cls) -> "JointLattice":
        return JointLattice(NotQubit(), const.Bottom())

    @classmethod
    def top(cls) -> "JointLattice":
        return JointLattice(AnyAddress(), const.Unknown())

    def join(self, other: "JointLattice"):
        return JointLattice(
            self.address.join(other.address), self.constant.join(other.constant)
        )

    def meet(self, other: "JointLattice") -> "JointLattice":
        return JointLattice(
            self.address.meet(other.address), self.constant.meet(other.constant)
        )

    def is_subseteq(self, other: "JointLattice") -> bool:
        return self.address.is_subseteq(other.address) and self.constant.is_subseteq(
            other.constant
        )
