"""Define the traits of the squin wire dialect.

`Threads` tells which result of a statement continues which linear operand. A
rewrite rule or an analysis reads it to follow one qubit from statement to
statement. `ReferenceForm` lets a statement of another dialect convert itself back
to reference squin.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from dataclasses import dataclass

from kirin import ir

from bloqade.types import is_subtype

from .kinds import Kind

StmtType = TypeVar("StmtType", bound=ir.Statement)


@dataclass(frozen=True)
class Threads(ir.StmtTrait, ABC, Generic[StmtType]):
    """Map each continued linear operand to its result.

    Each pair identifies the same qubit or register before and after the statement.
    For example, `Release` continues its register and consumes its borrowed wire.
    The implementation selects operands and results through the statement's typed fields.
    """

    @abstractmethod
    def threads(self, stmt: StmtType) -> list[tuple[ir.SSAValue, ir.ResultValue]]:
        """Return the operand and result pairs that preserve qubit or register identity."""
        ...


@dataclass(frozen=True)
class ReferenceForm(ir.StmtTrait, ABC):
    """Rebuild the reference form of a wire statement that another dialect owns.

    A dialect that adds statements to wire programs gives each one this trait.
    `WireToSquin` calls `rebuild` on each such statement. It then reads each result
    that a `Threads` pair continues as its operand, and deletes the statement.
    """

    @abstractmethod
    def rebuild(self, node: ir.Statement) -> tuple[ir.SSAValue, ...]:
        """Insert the reference statements of `node` before it and return new values.

        The result holds one value for each result of `node` that no `Threads`
        pair continues, in result order. A wire operand already reads as its qubit
        reference, so a reference statement can take it as a qubit.
        """


@dataclass(frozen=True)
class MatchesKind(ir.StmtTrait):
    """Check operand counts and parameter types against the operation kind."""

    broadcast: bool = False
    register: bool = False

    def verify(self, node: ir.Statement) -> None:
        """Require the operand counts that the operation kind declares."""
        attribute = node.attributes["kind"]
        assert isinstance(attribute, ir.PyAttr)
        kind = attribute.data
        assert isinstance(kind, Kind)
        linear = len(node.get_present_trait(Threads).threads(node))
        params = len(node.args) - linear
        count = linear
        if self.broadcast and linear > 0 and linear % kind.qubit_count == 0:
            count = kind.qubit_count
        if (count, params) != (kind.qubit_count, kind.param_count):
            noun = "register" if self.register else "wire"
            per = " per group" if self.broadcast else ""
            raise ir.ValidationError(
                node,
                f"'{kind.label}' needs {counted(kind.qubit_count, noun)}{per} and"
                f" {counted(kind.param_count, 'parameter')}, but it has"
                f" {linear} and {params}.",
            )

    def verify_types(self, node: ir.Statement) -> None:
        """Require each parameter to have the type that its operation kind declares."""
        self.verify(node)
        attribute = node.attributes["kind"]
        assert isinstance(attribute, ir.PyAttr)
        kind = attribute.data
        assert isinstance(kind, Kind)
        count = len(node.get_present_trait(Threads).threads(node))
        for index, (value, expected) in enumerate(
            zip(node.args[count:], kind.parameter_types, strict=True)
        ):
            if not is_subtype(value.type, expected):
                raise ir.ValidationError(
                    node,
                    f"Parameter {index} of '{kind.label}' requires {expected}, but got {value.type}.",
                )


def counted(count: int, noun: str) -> str:
    """Return the count with a singular or plural noun."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
