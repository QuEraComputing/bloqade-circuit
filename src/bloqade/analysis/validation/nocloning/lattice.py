from abc import abstractmethod
from typing import FrozenSet, final
from dataclasses import field, dataclass

from kirin.lattice import SingletonMeta, BoundedLattice


@dataclass
class QubitValidation(BoundedLattice["QubitValidation"]):
    r"""Base class for qubit-cloning validation lattice.

    Linear ordering (more precise --> less precise):
      Bottom ⊑ Must ⊑ May ⊑ Top

    Semantics:
      - Bottom: proven safe / never occurs
      - Must: definitely occurs (strong)
      - May: possibly occurs (weak)
      - Top: unknown / no information
    """

    @classmethod
    def bottom(cls) -> "QubitValidation":
        return Bottom()

    @classmethod
    def top(cls) -> "QubitValidation":
        return Top()

    @abstractmethod
    def is_subseteq(self, other: "QubitValidation") -> bool: ...

    @abstractmethod
    def join(self, other: "QubitValidation") -> "QubitValidation": ...

    @abstractmethod
    def meet(self, other: "QubitValidation") -> "QubitValidation": ...


@final
class Bottom(QubitValidation, metaclass=SingletonMeta):
    def is_subseteq(self, other: QubitValidation) -> bool:
        return True

    def join(self, other: QubitValidation) -> QubitValidation:
        return other

    def meet(self, other: QubitValidation) -> QubitValidation:
        return self

    def __repr__(self) -> str:
        return "⊥ (No Errors)"


@final
class Top(QubitValidation, metaclass=SingletonMeta):
    def is_subseteq(self, other: QubitValidation) -> bool:
        return isinstance(other, Top)

    def join(self, other: QubitValidation) -> QubitValidation:
        return self

    def meet(self, other: QubitValidation) -> QubitValidation:
        return other

    def __repr__(self) -> str:
        return "⊤ (Unknown)"


@final
@dataclass
class Must(QubitValidation):
    """Definite violations."""

    violations: FrozenSet[str] = field(default_factory=frozenset)

    def is_subseteq(self, other: QubitValidation) -> bool:
        match other:
            case Bottom():
                return False
            case Must(violations=ov):
                return self.violations.issubset(ov)
            case May(violations=_):
                return True
            case Top():
                return True
        return False

    def join(self, other: QubitValidation) -> QubitValidation:
        """Join with another validation state.

        Key insight: Must ⊔ Bottom = May (error on one path, not all)
        """
        match other:
            case Bottom():
                # Error in one branch, safe in other = May (conditional error)
                result = May(violations=self.violations)
                return result
            case Must(violations=ov):
                # Errors in both branches
                common = self.violations & ov
                all_violations = self.violations | ov
                if common == all_violations:
                    # Same errors on all paths = Must
                    return Must(violations=all_violations)
                else:
                    # Different errors on different paths = May
                    return May(violations=all_violations)
            case May(violations=ov):
                return May(violations=self.violations | ov)
            case Top():
                return Top()
        return Top()

    def meet(self, other: QubitValidation) -> QubitValidation:
        match other:
            case Bottom():
                return Bottom()
            case Must(violations=ov):
                inter = self.violations & ov
                return Must(violations=inter) if inter else Bottom()
            case May(violations=ov):
                inter = self.violations & ov if ov else self.violations
                return Must(violations=inter) if inter else Bottom()
            case Top():
                return self
        return Bottom()

    def __repr__(self) -> str:
        return f"Must({self.violations or '∅'})"


@final
@dataclass
class May(QubitValidation):
    """Potential violations."""

    violations: FrozenSet[str] = field(default_factory=frozenset)

    def is_subseteq(self, other: QubitValidation) -> bool:
        match other:
            case Bottom():
                return False
            case Must():
                return False
            case May(violations=ov):
                return self.violations.issubset(ov)
            case Top():
                return True
        return False

    def join(self, other: QubitValidation) -> QubitValidation:
        match other:
            case Bottom():
                return self
            case Must(violations=ov):
                return May(violations=self.violations | ov)
            case May(violations=ov):
                return May(violations=self.violations | ov)
            case Top():
                return Top()
        return Top()

    def meet(self, other: QubitValidation) -> QubitValidation:
        match other:
            case Bottom():
                return Bottom()
            case Must(violations=ov):
                inter = self.violations & ov if ov else ov or self.violations
                return Must(violations=inter) if inter else Bottom()
            case May(violations=ov):
                inter = self.violations & ov
                return May(violations=inter) if inter else Bottom()
            case Top():
                return self
        return Bottom()

    def __repr__(self) -> str:
        return f"May({self.violations or '∅'})"
