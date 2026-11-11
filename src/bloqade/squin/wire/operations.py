"""Share operand access across gates, noise channels, measurements and resets."""

from kirin import ir

from .traits import Threads, MatchesKind


class Operation(ir.Statement):
    """Give the gates, noise channels, measurements and resets one shared view.

    The `Threads` trait of each operation is the one record of its linear flow.
    `linear` holds the wires or registers that the operation consumes, and
    `outputs` holds the results that the trait pairs with those operands.
    `parameters` holds the classical operands, and `classical` holds the other
    results, such as measurement bits.
    """

    def verify_type(self) -> None:
        """Check the operand types and the parameter types that the operation kind requires."""
        super().verify_type()
        if (trait := self.get_trait(MatchesKind)) is not None:
            trait.verify_types(self)

    @property
    def linear(self) -> tuple[ir.SSAValue, ...]:
        """Return the wires or registers that the operation consumes."""
        threads = self.get_present_trait(Threads).threads(self)
        return tuple(operand for operand, _ in threads)

    @property
    def outputs(self) -> tuple[ir.ResultValue, ...]:
        """Return the results that continue `linear` in order."""
        threads = self.get_present_trait(Threads).threads(self)
        return tuple(result for _, result in threads)

    @property
    def parameters(self) -> tuple[ir.SSAValue, ...]:
        """Return classical operands in statement order, such as the angles of a gate."""
        linear = set(self.linear)
        return tuple(operand for operand in self.args if operand not in linear)

    @property
    def classical(self) -> tuple[ir.ResultValue, ...]:
        """Return classical results in statement order."""
        outputs = set(self.outputs)
        return tuple(result for result in self.results if result not in outputs)

    @property
    def label(self) -> str:
        """Return the name of the operation for messages."""
        return self.name

    @property
    def groups(self) -> tuple[tuple[ir.SSAValue, ...], ...]:
        """Return the groups of `linear` that the operation acts on at the same time.

        A `Gate` or a `Noise` splits `linear` into consecutive groups of one wire per
        qubit of its kind. For example, `Gate(kind=cx, wires=(c0, t0, c1, t1))` has
        the groups `(c0, t0)` and `(c1, t1)`. Every other operation has one group.
        """
        return (self.linear,)


class RegisterOperation(Operation):
    """Apply a single-wire operation at every position of whole registers.

    Position `i` of each register forms one group of wires. Unless the operation
    truncates, the program must give every register the same length.
    """

    @property
    def truncates(self) -> bool:
        """Check whether the operation stops at the shortest register."""
        return False

    def scalar(self, wires: tuple[ir.SSAValue, ...]) -> Operation:
        """Return the single-wire operation that this statement applies to `wires`."""
        raise NotImplementedError


def chunks(
    values: tuple[ir.SSAValue, ...], size: int
) -> tuple[tuple[ir.SSAValue, ...], ...]:
    """Split `values` into consecutive tuples of `size` values."""
    return tuple(values[k : k + size] for k in range(0, len(values), size))
