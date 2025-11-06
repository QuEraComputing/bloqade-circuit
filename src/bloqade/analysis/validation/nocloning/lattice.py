from abc import abstractmethod
from typing import FrozenSet, final
from dataclasses import field, dataclass

from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)


@dataclass
class QubitValidation(
    SimpleJoinMixin["QubitValidation"],
    SimpleMeetMixin["QubitValidation"],
    BoundedLattice["QubitValidation"],
):
    """Base class for qubit cloning validation lattice.

    Lattice ordering:
    Bottom ⊑ May{...} ⊑ Must{...} ⊑ Top
    """

    @classmethod
    def bottom(cls) -> "QubitValidation":
        """No violations detected"""
        return Bottom()

    @classmethod
    def top(cls) -> "QubitValidation":
        """Unknown state"""
        return Top()

    @abstractmethod
    def is_subseteq(self, other: "QubitValidation") -> bool:
        """Check if this state is a subset of another."""
        ...


@final
class Bottom(QubitValidation, metaclass=SingletonMeta):
    """Bottom element: no violations detected (safe)."""

    def is_subseteq(self, other: QubitValidation) -> bool:
        """Bottom is subset of everything."""
        return True

    def __repr__(self) -> str:
        return "⊥ (No Errors)"


@final
class Top(QubitValidation, metaclass=SingletonMeta):
    """Top element: unknown state (worst case - assume violations possible)."""

    def is_subseteq(self, other: QubitValidation) -> bool:
        """Top is only subset of Top."""
        return isinstance(other, Top)

    def __repr__(self) -> str:
        return "⊤ (Unknown)"


@final
@dataclass
class May(QubitValidation):
    """Potential violations that may occur depending on runtime values.

    Used when we have unknown addresses (UnknownQubit, UnknownReg, Unknown).
    """

    violations: FrozenSet[str] = field(default_factory=frozenset)

    def is_subseteq(self, other: QubitValidation) -> bool:
        """May ⊑ May' if violations ⊆ violations'
        May ⊑ Must (any may is less precise than must)
        May ⊑ Top
        """
        match other:
            case Bottom():
                return False
            case May(violations=other_violations):
                return self.violations.issubset(other_violations)
            case Must():
                return True  # May is less precise than Must
            case Top():
                return True
        return False

    def __repr__(self) -> str:
        if not self.violations:
            return "MayError(∅)"
        return f"MayError({self.violations})"


@final
@dataclass
class Must(QubitValidation):
    """Definite violations with concrete qubit addresses.

    These are violations we can prove will definitely occur.
    """

    violations: FrozenSet[str] = field(default_factory=frozenset)

    def is_subseteq(self, other: QubitValidation) -> bool:
        """Must ⊑ Must' if violations ⊆ violations'
        Must ⊑ Top
        """
        match other:
            case Bottom() | May():
                return False
            case Must(violations=other_violations):
                return self.violations.issubset(other_violations)
            case Top():
                return True
        return False

    def __repr__(self) -> str:
        if not self.violations:
            return "MustError(∅)"
        return f"MustError({self.violations})"
