"""This module holds the lattice of references that the reference analysis computes."""

from dataclasses import field, dataclass

from kirin import ir, types
from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)


@dataclass(frozen=True, repr=False)
class Returned:
    """A root that a call allocates and returns at one position of its result.

    `call` is a statement with kirin's `StaticCall` trait. `inner` is the root
    inside the callee that the call returns at `position`.
    """

    call: ir.Statement
    position: int
    inner: "Root"

    @property
    def callee(self) -> ir.Method:
        """Return the method that the call invokes, through kirin's `StaticCall`."""
        return self.call.get_present_trait(ir.StaticCall).get_callee(self.call)

    def __repr__(self) -> str:
        """Return the call result that holds the root and its origin in the callee.

        The form is `%x = make()[0]`. A result that packs several outputs in a tuple
        prints as `%pair[1] = make()[1]`. A result without a name prints as
        `make()[0]`.
        """
        origin = f"{self.callee.sym_name}()[{self.position}]"
        results = self.call.results
        packed = len(results) == 1
        value = results[0] if packed else results[self.position]
        if not value.name:
            return origin
        if packed and self.callee.return_type.is_subseteq(types.Tuple):
            return f"%{value.name}[{self.position}] = {origin}"
        return f"%{value.name} = {origin}"


Root = ir.SSAValue | Returned
"""An owner of tracked state: an allocation, a parameter, or a `Returned` root."""

CARRIED = "a value carried by a loop or branch"
"""The reason of an `Unknown` that a join of two different references produces."""


class Ref(SimpleJoinMixin["Ref"], SimpleMeetMixin["Ref"], BoundedLattice["Ref"]):
    """A lattice element that states what a value refers to.

    The join of two different references is `Unknown`.
    """

    @classmethod
    def top(cls) -> "Ref":
        """Return `Unknown` with the reason `CARRIED`."""
        return Unknown(CARRIED)

    @classmethod
    def bottom(cls) -> "Ref":
        """Return the element of a value that the analysis never reached."""
        return Bottom()

    def is_subseteq(self, other: "Ref") -> bool:
        """Return True if `other` is `Unknown` or equal to `self`."""
        return isinstance(other, Unknown) or self == other


def _name(value: ir.SSAValue) -> str:
    """Return the printed name of an SSA value, such as `%qs`."""
    return f"%{value.name}" if value.name else "%?"


def _owner(root: Root) -> str:
    """Return the printed name of a root."""
    return repr(root) if isinstance(root, Returned) else _name(root)


@dataclass(frozen=True, repr=False)
class Whole(Ref):
    """A reference to one item of tracked state, such as one qubit."""

    root: Root

    def __repr__(self) -> str:
        """Return the short form, such as `Whole(%q)`."""
        return f"Whole({_owner(self.root)})"


@dataclass(frozen=True, repr=False)
class Register(Ref):
    """A reference to a whole register, which holds items of tracked state."""

    root: Root

    def __repr__(self) -> str:
        """Return the short form, such as `Register(%qs)`."""
        return f"Register({_owner(self.root)})"


@dataclass(frozen=True, repr=False)
class Slot(Ref):
    """A reference to one item of a register root.

    If the register has a static length, a constant index lies in the range 0 to the
    length minus 1.
    """

    root: Root
    index: int | ir.SSAValue

    def __repr__(self) -> str:
        """Return the short form, such as `Slot(%qs, 2)`."""
        at = self.index if isinstance(self.index, int) else _name(self.index)
        return f"Slot({_owner(self.root)}, {at})"


@dataclass(frozen=True, repr=False)
class Members(Ref):
    """A value that holds other values, with one reference for each member.

    The join of two different member tuples is `Unknown`, even if some members are
    equal.
    """

    refs: tuple[Ref, ...]


@dataclass(frozen=True, repr=False)
class Items(Members):
    """The references of the items of a literal list."""

    def __repr__(self) -> str:
        """Return the short form, such as `[Whole(%a), Whole(%b)]`."""
        return "[" + ", ".join(map(repr, self.refs)) + "]"


@dataclass(frozen=True, repr=False)
class Positions(Members):
    """The references of the positions of a tuple."""

    def __repr__(self) -> str:
        """Return the short form, such as `(Whole(%a), Untracked)`."""
        return "(" + ", ".join(map(repr, self.refs)) + ")"


@dataclass(frozen=True, repr=False)
class Untracked(Ref, metaclass=SingletonMeta):
    """A value that refers to no tracked state."""

    def __repr__(self) -> str:
        """Return `Untracked`."""
        return "Untracked"


@dataclass(frozen=True, repr=False)
class Unknown(Ref):
    """A value that may refer to tracked state that the analysis cannot name.

    `Unknown` is the top element. The reason explains the lost information, and it
    does not take part in equality.
    """

    reason: str = field(compare=False, hash=False)

    def __repr__(self) -> str:
        """Return the reason, such as `Unknown: a slice of a register`."""
        return f"Unknown: {self.reason}"


@dataclass(frozen=True, repr=False)
class Bottom(Ref, metaclass=SingletonMeta):
    """A value that the analysis never reached, the bottom element."""

    def is_subseteq(self, other: Ref) -> bool:
        """Return True, because bottom lies below every element."""
        return True

    def __repr__(self) -> str:
        """Return `Bottom`."""
        return "Bottom"


UNTRACKED = Untracked()
