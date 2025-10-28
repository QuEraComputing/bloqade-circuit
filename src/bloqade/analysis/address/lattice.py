from typing import Sequence, final
from dataclasses import dataclass

from kirin import ir, types
from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)
from kirin.analysis import const
from kirin.dialects import ilist
from kirin.ir.attrs.abc import LatticeAttributeMeta

from bloqade.types import QubitType


@dataclass
class Address(
    SimpleJoinMixin["Address"],
    SimpleMeetMixin["Address"],
    BoundedLattice["Address"],
):

    @classmethod
    def bottom(cls) -> "Address":
        return Bottom()

    @classmethod
    def top(cls) -> "Address":
        return Unknown()

    @classmethod
    def from_type(cls, typ: types.TypeAttribute):
        if typ.is_subseteq(ilist.IListType[QubitType]):
            return UnknownReg()
        elif typ.is_subseteq(QubitType):
            return UnknownQubit()
        else:
            return Unknown()


@final
class Bottom(Address, metaclass=SingletonMeta):
    """Error during interpretation"""

    def is_subseteq(self, other: Address) -> bool:
        return True


@final
class Unknown(Address, metaclass=SingletonMeta):
    """Can't determine if it is an address or constant."""

    def is_subseteq(self, other: Address) -> bool:
        return isinstance(other, Unknown)


@final
@dataclass
class ConstResult(Address):
    """Stores a constant prop result in the lattice"""

    result: const.Result

    def is_subseteq(self, other: Address) -> bool:
        return isinstance(other, ConstResult) and self.result.is_subseteq(other.result)


@final
@dataclass
class UnknownQubit(Address, metaclass=SingletonMeta):
    """A lattice element representing a single qubit with an unknown address."""

    def is_subseteq(self, other: Address) -> bool:
        return isinstance(other, UnknownQubit)


@final
@dataclass
class UnknownReg(Address, metaclass=SingletonMeta):
    """A lattice element representing a container of qubits with unknown indices."""

    def is_subseteq(self, other: Address) -> bool:
        return isinstance(other, UnknownReg)


@final
@dataclass
class AddressQubit(Address):
    """A lattice element representing a single qubit with a known address."""

    data: int

    def is_subseteq(self, other: Address) -> bool:
        if isinstance(other, AddressQubit):
            return self.data == other.data
        return False


@final
@dataclass
class AddressReg(Address):
    """A lattice element representing a container of qubits with known indices."""

    data: Sequence[int]

    def is_subseteq(self, other: Address) -> bool:
        return isinstance(other, AddressReg) and self.data == other.data

    @property
    def qubits(self) -> tuple[AddressQubit, ...]:
        return tuple(AddressQubit(i) for i in self.data)


@final
@dataclass
class PartialLambda(Address):
    """Represents a partially known lambda function"""

    argnames: list[str]
    code: ir.Statement
    captured: tuple[Address, ...]

    def join(self, other: Address) -> Address:
        if other is other.bottom():
            return self

        if not isinstance(other, PartialLambda):
            return self.top().join(other)  # widen self

        if self.code is not other.code:
            return self.top()  # lambda stmt is pure

        if len(self.captured) != len(other.captured):
            return self.bottom()  # err

        return PartialLambda(
            self.argnames,
            self.code,
            tuple(x.join(y) for x, y in zip(self.captured, other.captured)),
        )

    def meet(self, other: Address) -> Address:
        if not isinstance(other, PartialLambda):
            return self.top().meet(other)

        if self.code is not other.code:
            return self.bottom()

        if len(self.captured) != len(other.captured):
            return self.top()

        return PartialLambda(
            self.argnames,
            self.code,
            tuple(x.meet(y) for x, y in zip(self.captured, other.captured)),
        )

    def is_subseteq(self, other: Address) -> bool:
        return (
            isinstance(other, PartialLambda)
            and self.code is other.code
            and self.argnames == other.argnames
            and len(self.captured) == len(other.captured)
            and all(
                self_ele.is_subseteq(other_ele)
                for self_ele, other_ele in zip(self.captured, other.captured)
            )
        )


@dataclass
class StaticContainer(Address):
    """A lattice element representing the results of any static container, e. g. ilist or tuple."""

    data: tuple[Address, ...]

    @classmethod
    def new(cls, data: tuple[Address, ...]):
        return cls(data)

    def join(self, other: "Address") -> "Address":
        if isinstance(other, type(self)) and len(self.data) == len(other.data):
            return self.new(tuple(x.join(y) for x, y in zip(self.data, other.data)))
        return self.top()

    def meet(self, other: "Address") -> "Address":
        if isinstance(other, type(self)) and len(self.data) == len(other.data):
            return self.new(tuple(x.meet(y) for x, y in zip(self.data, other.data)))
        return self.bottom()

    def is_subseteq(self, other: "Address") -> bool:
        return (
            isinstance(other, type(self))
            and len(self.data) == len(other.data)
            and all(x.is_subseteq(y) for x, y in zip(self.data, other.data))
        )


class PartialIListMeta(LatticeAttributeMeta):
    """This metaclass assures that PartialILists of ConstResults or AddressQubits are canonicalized
    to a single ConstResult or AddressReg respectively.

    because AddressReg is a specialization of PartialIList, being a container of pure qubit
    addresses. For Operations that act in generic containers (e.g., ilist.ForEach),
    AddressReg is treated as PartialIList but for other types of analysis it is often
    useful to distinguish between a generic IList and a pure qubit address list.

    Inside the method tables the `GetValuesMixin` implements a method that effectively
    undoes this canonicalization.

    """

    def __call__(cls, data: tuple[Address, ...]):
        # TODO: when constant prop has PartialIList, make sure to canonicalize here.
        if types.is_tuple_of(data, ConstResult) and types.is_tuple_of(
            all_constants := tuple(ele.result for ele in data), const.Value
        ):
            # all constants, create constant list
            return ConstResult(
                const.Value(ilist.IList([ele.data for ele in all_constants]))
            )
        elif types.is_tuple_of(data, AddressQubit):
            # all qubits create qubit register
            return AddressReg(tuple(ele.data for ele in data))
        else:
            return super().__call__(data)


@final
class PartialIList(StaticContainer, metaclass=PartialIListMeta):
    """A lattice element representing a partially known ilist."""


class PartialTupleMeta(LatticeAttributeMeta):
    """This metaclass assures that PartialTuples of ConstResults are canonicalized to a single ConstResult."""

    def __call__(cls, data: tuple[Address, ...]):
        if not types.is_tuple_of(data, ConstResult):
            return super().__call__(data)

        return ConstResult(const.PartialTuple(tuple(ele.result for ele in data)))


@final
class PartialTuple(StaticContainer, metaclass=PartialTupleMeta):
    """A lattice element representing a partially known tuple."""
