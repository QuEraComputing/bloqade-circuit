"""Define the traits of the squin wire dialect.

`Threads` tells which result of a statement continues which linear operand. A
rewrite rule or an analysis reads it to follow one qubit from statement to
statement. `ReferenceForm` lets a statement of another dialect convert itself back
to reference squin.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from kirin import ir


@dataclass(frozen=True)
class Threads(ir.StmtTrait):
    """Continue the linear operands in the field `field` with the leading results.

    The field holds one wire or register, or a tuple of them. Result `i` of the
    statement is the same qubit or register as operand `i` of the field. For example,
    `Release` has `Threads("register")`, so its result is the register that it fills,
    and its `wire` operand ends there. A statement without this trait continues none
    of its operands, such as `PackRegister`, which makes a new register.
    """

    field: str

    def threads(self, stmt: ir.Statement) -> list[tuple[ir.SSAValue, ir.ResultValue]]:
        """Return each operand of the field with the result that continues it."""
        value = getattr(stmt, self.field)
        operands = value if isinstance(value, tuple) else (value,)
        return list(zip(operands, stmt.results))


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
