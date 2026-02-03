from abc import abstractmethod
from typing import FrozenSet, final
from dataclasses import field, dataclass

from kirin.lattice import SingletonMeta, BoundedLattice


@dataclass
class QubitValidation(BoundedLattice["QubitValidation"]):
    r"""Base class for qubit-cloning validation lattice.

    Semantics for control flow:
      - Bottom: proven safe / never occurs
      - Must: definitely occurs on ALL paths
      - May: possibly occurs on SOME paths
      - Top: unknown / no information

    Lattice ordering (more precise --> less precise):
      Bottom ⊑ Must ⊑ May ⊑ Top
      Bottom ⊑ May ⊑ Top

    Key insight: Must ⊔ Bottom = May (happens on some paths, not all)
    """

    @classmethod
    def bottom(cls) -> "Bottom":
        return Bottom()

    @classmethod
    def top(cls) -> "Top":
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
    """Definite violations with concrete qubit IDs and gate names."""

    violations: FrozenSet[tuple[int, str]] = field(default_factory=frozenset)
    """Set of (qubit_id, gate_name) tuples"""

    def is_subseteq(self, other: QubitValidation) -> bool:
        match other:
            case Bottom():
                return False
            case Must(violations=ov):
                return self.violations.issubset(ov)
            case May() | Top():
                return True
        return False

    def join(self, other: QubitValidation) -> QubitValidation:
        match other:
            case Bottom():
                may_violations = frozenset((gate, "") for _, gate in self.violations)
                return May(violations=may_violations)
            case Must(violations=ov):
                merged = self.violations | ov
                return Must(violations=merged)
            case May(violations=ov):
                may_viols = frozenset((gate, "") for _, gate in self.violations)
                return May(violations=may_viols | ov)
            case Top():
                return other
        return Top()

    def meet(self, other: QubitValidation) -> QubitValidation:
        match other:
            case Bottom():
                return other
            case Must(violations=ov):
                inter = self.violations & ov
                return Must(violations=inter) if inter else Bottom()
            case May():
                return self
            case Top():
                return self
        return Bottom()

    def __repr__(self) -> str:
        if not self.violations:
            return "Must(∅)"
        viols = ", ".join(f"Qubit[{qid}] at {gate}" for qid, gate in self.violations)
        return f"Must({{{viols}}})"


@final
@dataclass
class May(QubitValidation):
    """Potential violations with gate names and conditions."""

    violations: FrozenSet[tuple[str, str]] = field(default_factory=frozenset)
    """Set of (gate_name, condition) tuples"""

    def is_subseteq(self, other: QubitValidation) -> bool:
        match other:
            case Bottom() | Must():
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
                may_viols = frozenset((gate, "") for _, gate in ov)
                return May(violations=self.violations | may_viols)
            case May(violations=ov):
                return May(violations=self.violations | ov)
            case Top():
                return other
        return Top()

    def meet(self, other: QubitValidation) -> QubitValidation:
        match other:
            case Bottom():
                return other
            case Must():
                return other
            case May(violations=ov):
                inter = self.violations & ov
                return May(violations=inter) if inter else Bottom()
            case Top():
                return self
        return Bottom()

    def __repr__(self) -> str:
        if not self.violations:
            return "May(∅)"
        viols = ", ".join(f"{gate}{cond}" for gate, cond in self.violations)
        return f"May({{{viols}}})"
