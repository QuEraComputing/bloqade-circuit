from typing import final
from dataclasses import field, dataclass

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
class AddressQubit(Address):
    data: int

    def is_subseteq(self, other: Address) -> bool:
        if isinstance(other, AddressQubit):
            return self.data == other.data
        return False


class Joint(
    SimpleJoinMixin["Joint"],
    SimpleMeetMixin["Joint"],
    BoundedLattice["Joint"],
    metaclass=LatticeAttributeMeta,
):
    @classmethod
    def bottom(cls) -> "Joint":
        return JointResult(Address.bottom(), const.Result.bottom())

    @classmethod
    def top(cls) -> "Joint":
        return JointResult(Address.top(), const.Result.top())

    def get_constant(self) -> const.Result:
        return const.Result.top()


@dataclass
class JointResult(Joint):
    qubit: Address = field(default_factory=Address.top)
    constant: const.Result = field(default_factory=const.Result.top)

    def __post_init__(self):
        assert isinstance(self.qubit, Address)
        assert isinstance(self.constant, const.Result)

    def get_constant(self) -> const.Result:
        return self.constant

    def join(self, other: "Joint"):
        if isinstance(other, JointResult):
            return JointResult(
                self.qubit.join(other.qubit), self.constant.join(other.constant)
            )

        return self.top()

    def meet(self, other: "Joint") -> "Joint":
        if isinstance(other, JointResult):
            return JointResult(
                self.qubit.meet(other.qubit), self.constant.meet(other.constant)
            )

        return self.bottom()

    def is_subseteq(self, other: "Joint") -> bool:
        if isinstance(other, JointResult):
            return self.qubit.is_subseteq(other.qubit) and self.constant.is_subseteq(
                other.constant
            )

        return False


@final
@dataclass
class JointMethod(Joint):
    argnames: list[str]
    code: ir.Statement
    captured: tuple[Joint, ...]

    def join(self, other: Joint) -> Joint:
        if other is other.bottom():
            return self

        if not isinstance(other, JointMethod):
            return self.top().join(other)  # widen self

        if self.code is not other.code:
            return self.top()  # lambda stmt is pure

        if len(self.captured) != len(other.captured):
            return self.bottom()  # err

        return JointMethod(
            self.argnames,
            self.code,
            tuple(x.join(y) for x, y in zip(self.captured, other.captured)),
        )

    def meet(self, other: Joint) -> Joint:
        if not isinstance(other, JointMethod):
            return self.top().meet(other)

        if self.code is not other.code:
            return self.bottom()

        if len(self.captured) != len(other.captured):
            return self.top()

        return JointMethod(
            self.argnames,
            self.code,
            tuple(x.meet(y) for x, y in zip(self.captured, other.captured)),
        )

    def is_subseteq(self, other: Joint) -> bool:
        return (
            isinstance(other, JointMethod)
            and self.code is other.code
            and self.argnames == other.argnames
            and len(self.captured) == len(other.captured)
            and all(
                self_ele.is_subseteq(other_ele)
                for self_ele, other_ele in zip(self.captured, other.captured)
            )
        )


@dataclass
class JointStaticContainer(Joint):
    """A lattice element representing the results of any static container, e. g. ilist or tuple."""

    data: tuple[Joint, ...]

    @classmethod
    def new(cls, data: tuple[Joint, ...]):
        return cls(data)

    def join(self, other: "Joint") -> "Joint":
        if isinstance(other, JointStaticContainer) and len(self.data) == len(
            other.data
        ):
            return self.new(tuple(x.join(y) for x, y in zip(self.data, other.data)))
        return self.top()

    def meet(self, other: "Joint") -> "Joint":
        if isinstance(other, type(self)) and len(self.data) == len(other.data):
            return self.new(tuple(x.meet(y) for x, y in zip(self.data, other.data)))
        return self.bottom()

    def is_subseteq(self, other: "Joint") -> bool:
        return (
            isinstance(other, type(self))
            and len(self.data) == len(other.data)
            and all(x.is_subseteq(y) for x, y in zip(self.data, other.data))
        )


class JointIListMeta(LatticeAttributeMeta):
    def __call__(cls, data: tuple[Joint, ...]):
        if not types.is_tuple_of(data, JointResult):
            return super().__call__(data)

        all_constants = tuple(ele.constant for ele in data)
        all_qubits = tuple(ele.qubit for ele in data)

        if not types.is_tuple_of(all_constants, const.Value):
            return super().__call__(data)

        if not types.is_tuple_of(all_qubits, NotQubit):
            return super().__call__(data)

        constant = const.Value(ilist.IList([ele.data for ele in all_constants]))

        return JointResult(NotQubit(), constant)


@final
class JointIList(JointStaticContainer, metaclass=JointIListMeta):
    pass


class JointTupleMeta(LatticeAttributeMeta):
    def __call__(cls, data: tuple[Joint, ...]):
        if not types.is_tuple_of(data, JointResult):
            return super().__call__(data)

        all_qubits = tuple(ele.qubit for ele in data)

        if not types.is_tuple_of(all_qubits, NotQubit):
            return super().__call__(data)

        all_constants = tuple(ele.constant for ele in data)
        constant = const.PartialTuple(all_constants)

        return JointResult(NotQubit(), constant)


@final
class JointTuple(JointStaticContainer, metaclass=JointTupleMeta):
    pass
