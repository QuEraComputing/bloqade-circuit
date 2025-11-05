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
    """Tracks cloning violations detected during analysis."""

    violations: FrozenSet[str] = field(default_factory=frozenset)

    @classmethod
    def bottom(cls) -> "QubitValidation":
        """No violations detected"""
        return Bottom()

    @classmethod
    def top(cls) -> "QubitValidation":
        """Unknown state - assume potential violations"""
        return Top()

    def is_subseteq(self, other: "QubitValidation") -> bool:
        """Check if this state is a subset of another.

        Lattice ordering:
        Bottom ⊑ {{'Qubit[1] at CX Gate'}} ⊑ {{'Qubit[0] at CX Gate'},{'Qubit[1] at CX Gate'}} ⊑ Top
        """
        if isinstance(other, Top):
            return True
        if isinstance(self, Bottom):
            return True
        if isinstance(other, Bottom):
            return False

        return self.violations.issubset(other.violations)

    def __repr__(self) -> str:
        """Custom repr to show violations clearly."""
        if not self.violations:
            return "QubitValidation()"
        return f"QubitValidation(violations={self.violations})"


@final
class Bottom(QubitValidation, metaclass=SingletonMeta):
    """Bottom element representing no violations."""

    def is_subseteq(self, other: QubitValidation) -> bool:
        """Bottom is subset of everything."""
        return True

    def __repr__(self) -> str:
        """Cleaner printing."""
        return "⊥ (Bottom)"


@final
class Top(QubitValidation, metaclass=SingletonMeta):
    """Top element representing unknown state with potential violations."""

    def is_subseteq(self, other: QubitValidation) -> bool:
        """Top is only subset of Top."""
        return isinstance(other, Top)

    def __repr__(self) -> str:
        """Cleaner printing."""
        return "⊤ (Top)"
