"""Define the wire noise dialect and its scalar and register statements."""

from dataclasses import dataclass

from kirin import ir, types
from kirin.decl import info, statement

from .kinds import NoiseKind
from .types import WireType, RegisterType
from .traits import Threads, MatchesKind, ReferenceForm
from .operations import Operation, RegisterOperation, chunks

dialect = ir.Dialect("squin.wire.noise")


class NoiseThreads(Threads["Noise"]):
    """Continue each wire of a noise through the corresponding result."""

    def threads(self, stmt: "Noise") -> list[tuple[ir.SSAValue, ir.ResultValue]]:
        """Pair every wire operand with its result in order."""
        return list(zip(stmt.wires, stmt.results, strict=True))


class RegisterNoiseThreads(Threads["RegisterNoise"]):
    """Continue each register of a noise through the corresponding result."""

    def threads(
        self, stmt: "RegisterNoise"
    ) -> list[tuple[ir.SSAValue, ir.ResultValue]]:
        """Pair every register operand with its result in order."""
        return list(zip(stmt.registers, stmt.results, strict=True))


@statement(dialect=dialect, init=False)
class Noise(Operation):
    """Apply the noise channel `kind` to each group of wires at the same time.

    Each group holds one wire per qubit of the channel, and the groups share no
    qubit. `params` holds the probabilities. Result `i` continues wire `i`.
    """

    name = "noise"
    traits = frozenset({NoiseThreads(), MatchesKind(broadcast=True)})
    wires: tuple[ir.SSAValue, ...] = info.argument(WireType)
    params: tuple[ir.SSAValue, ...] = info.argument()
    kind: NoiseKind = info.attribute()

    def __init__(
        self,
        kind: NoiseKind,
        wires: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...] = (),
    ) -> None:
        """Build the noise channel `kind` on `wires` with the probabilities `params`."""
        super().__init__(
            args=(*wires, *params),
            result_types=tuple(WireType for _ in wires),
            args_slice={
                "wires": slice(0, len(wires)),
                "params": slice(len(wires), None),
            },
            attributes={"kind": ir.PyAttr(kind)},
        )

    @property
    def label(self) -> str:
        """Return the channel kind."""
        return self.kind.label

    @property
    def groups(self) -> tuple[tuple[ir.SSAValue, ...], ...]:
        """Return the groups of one wire per qubit of the kind."""
        return chunks(self.linear, self.kind.qubit_count)


@statement(dialect=dialect, init=False)
class RegisterNoise(RegisterOperation):
    """Apply the noise channel `kind` at every position of whole registers."""

    name = "register_noise"
    traits = frozenset({RegisterNoiseThreads(), MatchesKind(register=True)})
    registers: tuple[ir.SSAValue, ...] = info.argument(RegisterType)
    params: tuple[ir.SSAValue, ...] = info.argument()
    kind: NoiseKind = info.attribute()

    def __init__(
        self,
        kind: NoiseKind,
        registers: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...] = (),
    ) -> None:
        """Build the noise channel `kind` on `registers` with `params`."""
        super().__init__(
            args=(*registers, *params),
            result_types=tuple(RegisterType for _ in registers),
            args_slice={
                "registers": slice(0, len(registers)),
                "params": slice(len(registers), None),
            },
            attributes={"kind": ir.PyAttr(kind)},
        )

    @property
    def label(self) -> str:
        """Return the channel kind."""
        return self.kind.label

    @property
    def truncates(self) -> bool:
        """Check whether the kind stops at the shortest register."""
        return self.kind.truncates

    def scalar(self, wires: tuple[ir.SSAValue, ...]) -> Noise:
        """Return the noise channel on one wire per register."""
        return Noise(self.kind, wires, tuple(self.params))


@dataclass(frozen=True)
class CorrelatedLossReference(ReferenceForm):
    """Reconstruct one group whose qubits share the same loss event."""

    def rebuild(self, node: ir.Statement) -> tuple[ir.SSAValue, ...]:
        """Insert the source noise operation on one list of qubits."""
        from kirin.dialects import ilist

        from bloqade.types import QubitType
        from bloqade.squin.noise.stmts import CorrelatedQubitLoss

        assert isinstance(node, CorrelatedLoss)
        groups = ilist.New(
            (node.register,), elem_type=ilist.IListType[QubitType, types.Any]
        )
        groups.insert_before(node)
        CorrelatedQubitLoss(node.probability, groups.result).insert_before(node)
        return ()


class CorrelatedLossThreads(Threads["CorrelatedLoss"]):
    """Continue the register through a correlated loss event."""

    def threads(
        self, stmt: "CorrelatedLoss"
    ) -> list[tuple[ir.SSAValue, ir.ResultValue]]:
        """Pair the register operand with its continued result."""
        return [(stmt.register, stmt.register_out)]


@statement(dialect=dialect)
class CorrelatedLoss(ir.Statement):
    """Apply one correlated loss event to every qubit of a register."""

    name = "correlated_loss"
    traits = frozenset({CorrelatedLossThreads(), CorrelatedLossReference()})
    register: ir.SSAValue = info.argument(RegisterType)
    probability: ir.SSAValue = info.argument(types.Float)
    register_out: ir.ResultValue = info.result(RegisterType)
