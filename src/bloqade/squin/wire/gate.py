"""Define the wire gate dialect and its scalar and register statements."""

from kirin import ir
from kirin.decl import info, statement

from .kinds import GateKind
from .types import WireType, RegisterType
from .traits import Threads, MatchesKind
from .operations import Operation, RegisterOperation, chunks

dialect = ir.Dialect("squin.wire.gate")


@statement(dialect=dialect, init=False)
class Gate(Operation):
    """Apply the unitary gate `kind` to each group of wires at the same time.

    Each group holds one wire per qubit of the gate, and the groups share no
    qubit. `params` holds the angles in turns. Result `i` continues wire `i`.
    """

    name = "gate"
    traits = frozenset({Threads("wires"), MatchesKind(broadcast=True)})
    wires: tuple[ir.SSAValue, ...] = info.argument(WireType)
    params: tuple[ir.SSAValue, ...] = info.argument()
    kind: GateKind = info.attribute()
    adjoint: bool = info.attribute(default=False)

    def __init__(
        self,
        kind: GateKind,
        wires: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...] = (),
        *,
        adjoint: bool = False,
    ) -> None:
        """Build the gate `kind` on `wires` with the angles `params`."""
        super().__init__(
            args=(*wires, *params),
            result_types=tuple(WireType for _ in wires),
            args_slice={
                "wires": slice(0, len(wires)),
                "params": slice(len(wires), None),
            },
            attributes={"kind": ir.PyAttr(kind), "adjoint": ir.PyAttr(adjoint)},
        )

    @property
    def label(self) -> str:
        """Return the gate kind."""
        return self.kind.label

    @property
    def groups(self) -> tuple[tuple[ir.SSAValue, ...], ...]:
        """Return the groups of one wire per qubit of the kind."""
        return chunks(self.linear, self.kind.qubit_count)


@statement(dialect=dialect, init=False)
class RegisterGate(RegisterOperation):
    """Apply the gate `kind` at every position of one register per qubit of the gate."""

    name = "register_gate"
    traits = frozenset({Threads("registers"), MatchesKind(register=True)})
    registers: tuple[ir.SSAValue, ...] = info.argument(RegisterType)
    params: tuple[ir.SSAValue, ...] = info.argument()
    kind: GateKind = info.attribute()
    adjoint: bool = info.attribute(default=False)

    def __init__(
        self,
        kind: GateKind,
        registers: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...] = (),
        *,
        adjoint: bool = False,
    ) -> None:
        """Build the gate `kind` on `registers` with the angles `params`."""
        super().__init__(
            args=(*registers, *params),
            result_types=tuple(RegisterType for _ in registers),
            args_slice={
                "registers": slice(0, len(registers)),
                "params": slice(len(registers), None),
            },
            attributes={"kind": ir.PyAttr(kind), "adjoint": ir.PyAttr(adjoint)},
        )

    @property
    def label(self) -> str:
        """Return the gate kind."""
        return self.kind.label

    @property
    def truncates(self) -> bool:
        """Check whether the kind stops at the shortest register."""
        return self.kind.truncates

    def scalar(self, wires: tuple[ir.SSAValue, ...]) -> Gate:
        """Return the gate on one wire per register."""
        return Gate(self.kind, wires, tuple(self.params), adjoint=self.adjoint)
