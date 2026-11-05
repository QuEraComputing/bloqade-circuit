"""Define the statements of the squin wire dialect.

`Alloc` and `Free` start and end the life of one qubit. `AllocRegister` and
`FreeRegister` do the same for a list of qubits. `Borrow` and `Release` lend one
qubit of a register to a wire and put it back. `Take` and `Put` move a qubit out of
a register for good and fill an empty element, and `TakeSlice` and `PutSlice` do the
same for a range. `Length` reads the size of a register.

A complete register holds a qubit in each element. A borrowed element must come
back before the register leaves through a free, a yield, a return or a call. A taken
element can stay empty until `DiscardRegister` frees the register.

A statement whose result continues one of its wires or registers has a `Threads`
trait. `PackRegister`, `SplitRegister` and `JoinRegister` consume their inputs and
make new registers, and the frees end their inputs, so these statements have none.

`Gate`, `Noise`, `Measure` and `Reset` act on single wires. Their register forms
act at every position of whole registers. A gate or a noise channel names its
operation with a kind from `kinds.py`.
"""

from dataclasses import dataclass

from kirin import ir, types
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import MeasurementResultType

from .kinds import GateKind, NoiseKind
from .types import WireType, RegisterType
from .traits import Threads
from ._dialect import dialect


@statement(dialect=dialect)
class Alloc(ir.Statement):
    """Allocate one qubit in the zero state and return its wire."""

    name = "alloc"
    result: ir.ResultValue = info.result(WireType)


@statement(dialect=dialect)
class Free(ir.Statement):
    """End the life of the qubit that `wire` carries."""

    name = "free"
    wire: ir.SSAValue = info.argument(WireType)


@statement(dialect=dialect)
class AllocRegister(ir.Statement):
    """Allocate `size` qubits in the zero state and return them as one register."""

    name = "alloc_register"
    size: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(RegisterType)


@statement(dialect=dialect)
class FreeRegister(ir.Statement):
    """End the life of every qubit of `register`."""

    name = "free_register"
    register: ir.SSAValue = info.argument(RegisterType)


@statement(dialect=dialect)
class Borrow(ir.Statement):
    """Lend the qubit at `index` of `register` to a wire.

    The element stays empty until a `Release` at the same index puts the qubit back.
    The register must get the qubit back before it leaves its region.
    """

    name = "borrow"
    traits = frozenset({Threads("register")})
    register: ir.SSAValue = info.argument(RegisterType)
    index: ir.SSAValue = info.argument(types.Int)
    register_out: ir.ResultValue = info.result(RegisterType)
    wire: ir.ResultValue = info.result(WireType)


@statement(dialect=dialect)
class Release(ir.Statement):
    """Put the qubit that `wire` carries back into `register` at `index`."""

    name = "release"
    traits = frozenset({Threads("register")})
    register: ir.SSAValue = info.argument(RegisterType)
    index: ir.SSAValue = info.argument(types.Int)
    wire: ir.SSAValue = info.argument(WireType)
    register_out: ir.ResultValue = info.result(RegisterType)


@statement(dialect=dialect)
class Length(ir.Statement):
    """Return `register` and the count of qubits that it holds."""

    name = "length"
    traits = frozenset({Threads("register")})
    register: ir.SSAValue = info.argument(RegisterType)
    register_out: ir.ResultValue = info.result(RegisterType)
    result: ir.ResultValue = info.result(types.Int)


@statement(dialect=dialect)
class Take(ir.Statement):
    """Move the qubit at `index` out of `register` for good, as a wire.

    The element stays empty until a `Put` fills it, or `DiscardRegister` frees the
    register.
    """

    name = "take"
    traits = frozenset({Threads("register")})
    register: ir.SSAValue = info.argument(RegisterType)
    index: ir.SSAValue = info.argument(types.Int)
    register_out: ir.ResultValue = info.result(RegisterType)
    wire: ir.ResultValue = info.result(WireType)


@statement(dialect=dialect)
class Put(ir.Statement):
    """Fill the empty element at `index` of `register` with the qubit of `wire`.

    The qubit can come from anywhere, such as a `Take` of another register.
    """

    name = "put"
    traits = frozenset({Threads("register")})
    register: ir.SSAValue = info.argument(RegisterType)
    index: ir.SSAValue = info.argument(types.Int)
    wire: ir.SSAValue = info.argument(WireType)
    register_out: ir.ResultValue = info.result(RegisterType)


@statement(dialect=dialect)
class PackRegister(ir.Statement):
    """Consume qubits and form a register in operand order."""

    name = "pack_register"
    wires: tuple[ir.SSAValue, ...] = info.argument(WireType)
    result: ir.ResultValue = info.result(RegisterType)


@statement(dialect=dialect)
class SplitRegister(ir.Statement):
    """Divide a complete register at `index` into 2 new registers."""

    name = "split_register"
    register: ir.SSAValue = info.argument(RegisterType)
    index: ir.SSAValue = info.argument(types.Int)
    before: ir.ResultValue = info.result(RegisterType)
    after: ir.ResultValue = info.result(RegisterType)


@statement(dialect=dialect)
class JoinRegister(ir.Statement):
    """Consume two complete registers and concatenate their qubits."""

    name = "join_register"
    first: ir.SSAValue = info.argument(RegisterType)
    second: ir.SSAValue = info.argument(RegisterType)
    result: ir.ResultValue = info.result(RegisterType)


@statement(dialect=dialect)
class TakeSlice(ir.Statement):
    """Move a contiguous range of `register` into a new register.

    The elements stay empty until `Put` or `PutSlice` fills them.
    """

    name = "take_slice"
    traits = frozenset({Threads("register")})
    register: ir.SSAValue = info.argument(RegisterType)
    start: ir.SSAValue = info.argument(types.Int)
    length: ir.SSAValue = info.argument(types.Int)
    register_out: ir.ResultValue = info.result(RegisterType)
    slice_register: ir.ResultValue = info.result(RegisterType)


@statement(dialect=dialect)
class PutSlice(ir.Statement):
    """Fill an empty contiguous range of `register` with the qubits of a register."""

    name = "put_slice"
    traits = frozenset({Threads("register")})
    register: ir.SSAValue = info.argument(RegisterType)
    start: ir.SSAValue = info.argument(types.Int)
    slice_register: ir.SSAValue = info.argument(RegisterType)
    register_out: ir.ResultValue = info.result(RegisterType)


@statement(dialect=dialect)
class DiscardRegister(ir.Statement):
    """Free the remaining qubits of `register`, whose taken elements can be empty."""

    name = "discard_register"
    register: ir.SSAValue = info.argument(RegisterType)


class Operation(ir.Statement):
    """Give the gates, noise channels, measurements and resets one shared view.

    The `Threads` trait of each operation is the one record of its linear flow.
    `linear` holds the wires or registers that the operation consumes, and
    `outputs` holds the leading results that continue them in the same order.
    `parameters` holds the classical operands, and `classical` holds the other
    results, such as measurement bits.
    """

    @property
    def linear(self) -> tuple[ir.SSAValue, ...]:
        """Return the wires or registers that the operation consumes."""
        threads = self.get_present_trait(Threads).threads(self)
        return tuple(operand for operand, _ in threads)

    @property
    def outputs(self) -> tuple[ir.ResultValue, ...]:
        """Return the results that continue `linear` in order."""
        return tuple(self.results[: len(self.linear)])

    @property
    def parameters(self) -> tuple[ir.SSAValue, ...]:
        """Return the operands after `linear` in order, such as the angles of a gate."""
        return tuple(self.args[len(self.linear) :])

    @property
    def classical(self) -> tuple[ir.ResultValue, ...]:
        """Return the results after `outputs` in order."""
        return tuple(self.results[len(self.linear) :])

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


def chunks(
    values: tuple[ir.SSAValue, ...], size: int
) -> tuple[tuple[ir.SSAValue, ...], ...]:
    """Split `values` into consecutive tuples of `size` values."""
    return tuple(values[k : k + size] for k in range(0, len(values), size))


@dataclass(frozen=True)
class MatchesKind(ir.StmtTrait):
    """Check that a gate or a noise channel has the operand counts of its kind.

    If `broadcast` is True, the statement can act on any positive number of groups,
    each with the qubit count of the kind. Kirin's generated `check` of each
    statement runs this trait.
    """

    broadcast: bool = False

    def verify(self, node: ir.Statement) -> None:
        """Raise a validation error if `node` has other operand counts than its kind."""
        assert isinstance(node, (Gate, Noise, RegisterGate, RegisterNoise))
        kind = node.kind
        linear, params = len(node.linear), len(node.params)
        if self.broadcast and linear > 0 and linear % kind.qubit_count == 0:
            linear = kind.qubit_count
        if (linear, params) != (kind.qubit_count, kind.param_count):
            noun = "register" if isinstance(node, RegisterOperation) else "wire"
            per = " per group" if self.broadcast else ""
            raise ir.ValidationError(
                node,
                f"'{kind.label}' needs {counted(kind.qubit_count, noun)}{per} and"
                f" {counted(kind.param_count, 'parameter')}, but it has"
                f" {len(node.linear)} and {params}.",
            )


def counted(count: int, noun: str) -> str:
    """Return `count` with `noun` in the right number, such as `1 wire` or `2 wires`."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


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
class Noise(Operation):
    """Apply the noise channel `kind` to each group of wires at the same time.

    Each group holds one wire per qubit of the channel, and the groups share no
    qubit. `params` holds the probabilities. Result `i` continues wire `i`.
    """

    name = "noise"
    traits = frozenset({Threads("wires"), MatchesKind(broadcast=True)})
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


@statement(dialect=dialect)
class Measure(Operation):
    """Measure the qubit of `wire`, keep it, and return its measurement result."""

    name = "measure"
    traits = frozenset({Threads("wire")})
    wire: ir.SSAValue = info.argument(WireType)
    wire_out: ir.ResultValue = info.result(WireType)
    bit: ir.ResultValue = info.result(MeasurementResultType)


@statement(dialect=dialect)
class Reset(Operation):
    """Reset the qubit of `wire` to the zero state."""

    name = "reset"
    traits = frozenset({Threads("wire")})
    wire: ir.SSAValue = info.argument(WireType)
    wire_out: ir.ResultValue = info.result(WireType)


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


@statement(dialect=dialect, init=False)
class RegisterGate(RegisterOperation):
    """Apply the gate `kind` at every position of one register per qubit of the gate."""

    name = "register_gate"
    traits = frozenset({Threads("registers"), MatchesKind()})
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


@statement(dialect=dialect, init=False)
class RegisterNoise(RegisterOperation):
    """Apply the noise channel `kind` at every position of whole registers."""

    name = "register_noise"
    traits = frozenset({Threads("registers"), MatchesKind()})
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


@statement(dialect=dialect)
class RegisterMeasure(RegisterOperation):
    """Measure every qubit of `register` and return the results in order."""

    name = "register_measure"
    traits = frozenset({Threads("register")})
    register: ir.SSAValue = info.argument(RegisterType)
    register_out: ir.ResultValue = info.result(RegisterType)
    bits: ir.ResultValue = info.result(
        ilist.IListType[MeasurementResultType, types.Any]
    )

    def scalar(self, wires: tuple[ir.SSAValue, ...]) -> Measure:
        """Return the measurement of one wire."""
        (wire,) = wires
        return Measure(wire)


@statement(dialect=dialect)
class RegisterReset(RegisterOperation):
    """Reset every qubit of `register` to the zero state."""

    name = "register_reset"
    traits = frozenset({Threads("register")})
    register: ir.SSAValue = info.argument(RegisterType)
    register_out: ir.ResultValue = info.result(RegisterType)

    def scalar(self, wires: tuple[ir.SSAValue, ...]) -> Reset:
        """Return the reset of one wire."""
        (wire,) = wires
        return Reset(wire)
