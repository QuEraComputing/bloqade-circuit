"""Define statements that mirror jeff's gate and Pauli-product rotation operations."""

from kirin import ir, types
from kirin.decl import info, statement

from bloqade.jeff.types import WireType

dialect = ir.Dialect("jeff.gate")


@statement(dialect=dialect, init=False)
class Gate(ir.Statement):
    """A statement that applies a named quantum gate with jeff's modifiers.

    The modifiers are `adjoint` and `power`.

    The angles in `params` are in radians. If `controls` is non-empty, the
    statement applies the controlled version of the gate. The results hold
    the output wires of `targets` first and the output wires of `controls`
    after them.
    """

    name = "gate"
    targets: tuple[ir.SSAValue, ...] = info.argument(WireType)
    controls: tuple[ir.SSAValue, ...] = info.argument(WireType)
    params: tuple[ir.SSAValue, ...] = info.argument(types.Float)
    gate_name: str = info.attribute()
    adjoint: bool = info.attribute(default=False)
    power: int = info.attribute(default=1)

    def __init__(
        self,
        targets: tuple[ir.SSAValue, ...],
        controls: tuple[ir.SSAValue, ...] = (),
        params: tuple[ir.SSAValue, ...] = (),
        *,
        gate_name: str,
        adjoint: bool = False,
        power: int = 1,
    ) -> None:
        """Build a statement that applies `gate_name` to `targets` and `controls`."""
        num_targets = len(targets)
        num_controls = len(controls)
        super().__init__(
            args=(*targets, *controls, *params),
            result_types=tuple(WireType for _ in range(num_targets + num_controls)),
            args_slice={
                "targets": slice(0, num_targets),
                "controls": slice(num_targets, num_targets + num_controls),
                "params": slice(num_targets + num_controls, None),
            },
            attributes={
                "gate_name": ir.PyAttr(gate_name),
                "adjoint": ir.PyAttr(adjoint),
                "power": ir.PyAttr(power),
            },
        )


@statement(dialect=dialect, init=False)
class Ppr(ir.Statement):
    """A statement that applies the Pauli-product rotation exp(i * angle * P).

    The Pauli product P comes from `pauli_string`, which holds one letter per
    target wire. For three targets, `("x", "i", "z")` is a valid string.
    The letters are "i", "x", "y" and "z".
    """

    name = "ppr"
    targets: tuple[ir.SSAValue, ...] = info.argument(WireType)
    controls: tuple[ir.SSAValue, ...] = info.argument(WireType)
    angle: ir.SSAValue = info.argument(types.Float)
    pauli_string: tuple[str, ...] = info.attribute()
    adjoint: bool = info.attribute(default=False)
    power: int = info.attribute(default=1)

    def __init__(
        self,
        targets: tuple[ir.SSAValue, ...],
        controls: tuple[ir.SSAValue, ...],
        angle: ir.SSAValue,
        *,
        pauli_string: tuple[str, ...],
        adjoint: bool = False,
        power: int = 1,
    ) -> None:
        """Build a Pauli-product rotation by `angle` on `targets` and `controls`."""
        num_targets = len(targets)
        num_controls = len(controls)
        super().__init__(
            args=(*targets, *controls, angle),
            result_types=tuple(WireType for _ in range(num_targets + num_controls)),
            args_slice={
                "targets": slice(0, num_targets),
                "controls": slice(num_targets, num_targets + num_controls),
                "angle": num_targets + num_controls,
            },
            attributes={
                "pauli_string": ir.PyAttr(tuple(pauli_string)),
                "adjoint": ir.PyAttr(adjoint),
                "power": ir.PyAttr(power),
            },
        )

    def verify(self) -> None:
        """Check that the Pauli string has one letter from i, x, y, z per target."""
        super().verify()
        if len(self.pauli_string) != len(self.targets):
            raise ir.ValidationError(
                self,
                f"a Pauli string of {len(self.pauli_string)} letters acts on "
                f"{len(self.targets)} targets",
            )
        for letter in self.pauli_string:
            if letter not in ("i", "x", "y", "z"):
                raise ir.ValidationError(self, f"'{letter}' is no Pauli letter")
