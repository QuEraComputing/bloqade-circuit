"""This module holds the traits of the squin wire dialect.

`Threads` tells which result of a statement continues which linear operand. A
rewrite rule or an analysis reads it to follow one qubit from statement to
statement. `ThreadsPairs` names fixed fields, and `ThreadsInOrder` pairs a tuple
field with the results in order. `ReferenceForm` lets a statement of another
dialect convert itself back to reference squin.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from kirin import ir


@dataclass(frozen=True)
class Threads(ir.StmtTrait, ABC):
    """Name the result that continues each linear operand of a statement."""

    @abstractmethod
    def threads(self, stmt: ir.Statement) -> list[tuple[ir.SSAValue, ir.ResultValue]]:
        """Return each linear operand of `stmt` with the result that continues it."""

    def successor(self, stmt: ir.Statement, operand: ir.SSAValue) -> ir.ResultValue:
        """Return the result of `stmt` that continues the linear operand `operand`."""
        for value, result in self.threads(stmt):
            if value is operand:
                return result
        raise ValueError(f"{operand} is no linear operand of {stmt.name}")


@dataclass(frozen=True)
class ThreadsPairs(Threads):
    """Pair fixed argument fields with the result fields that continue them.

    For example, `Release` has the pair `("register", "register_out")`.
    """

    pairs: tuple[tuple[str, str], ...]

    def threads(self, stmt: ir.Statement) -> list[tuple[ir.SSAValue, ir.ResultValue]]:
        """Return the value of each argument field with its result field."""
        return [(getattr(stmt, a), getattr(stmt, r)) for a, r in self.pairs]


@dataclass(frozen=True)
class ThreadsInOrder(Threads):
    """Continue item `i` of the tuple field `field` with result `i`.

    For example, `Gate` continues each wire of its `wires` field.
    """

    field: str

    def threads(self, stmt: ir.Statement) -> list[tuple[ir.SSAValue, ir.ResultValue]]:
        """Return each item of the tuple field with the result at its position."""
        return list(zip(getattr(stmt, self.field), stmt.results))


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
