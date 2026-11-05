"""Map each squin statement on qubits to the wire statements that the conversions use.

`SquinToWire`, `WireToSquin` and the Jeff importer read this table. An entry reads
the qubit-list fields, the classical fields and the results of its squin statement
from Kirin's statement schema. `check` compares the counts of each entry with its
kind when this module loads.
"""

from __future__ import annotations

from typing import TypeAlias, cast
from functools import cached_property
from dataclasses import dataclass
from collections.abc import Callable

from kirin import ir, types
from kirin.decl import fields
from kirin.dialects import ilist

from bloqade.qubit import stmts as qubit_stmts
from bloqade.types import QubitType, is_subtype, holds_qubits
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.squin.wire import (
    Gate,
    Noise,
    Reset,
    Measure,
    GateKind,
    NoiseKind,
    Operation,
    RegisterGate,
    RegisterNoise,
    RegisterReset,
    RegisterMeasure,
    RegisterOperation,
)
from bloqade.squin.noise import stmts as noise_stmts
from bloqade.squin.wire.kinds import Kind
from bloqade.native.dialects.gate import stmts as native_stmts


@dataclass(frozen=True)
class BaseEntry:
    """Name the fields of one squin statement on qubits, in operand order."""

    source: type[ir.Statement]
    """Hold the squin statement."""

    @cached_property
    def arguments(self) -> dict[str, types.TypeAttribute]:
        """Return the type of each argument field of the squin statement in order."""
        schema = fields(self.source)
        return {
            name: field.type
            for name, field in {**schema.std_args, **schema.kw_args}.items()
        }

    @cached_property
    def qubits(self) -> tuple[str, ...]:
        """Return the qubit-list fields of the squin statement."""
        return tuple(name for name, typ in self.arguments.items() if holds_qubits(typ))

    @cached_property
    def params(self) -> tuple[str, ...]:
        """Return the classical fields of the squin statement."""
        return tuple(name for name in self.arguments if name not in self.qubits)

    @cached_property
    def results(self) -> tuple[str, ...]:
        """Return the classical list results of the squin statement."""
        return tuple(fields(self.source).results)

    @cached_property
    def has_adjoint(self) -> bool:
        """Check whether the squin statement has the attribute `adjoint`."""
        return "adjoint" in fields(self.source).attributes

    @property
    def truncates(self) -> bool:
        """Check whether the register form stops at the shortest register."""
        return False

    @property
    def broadcast(self) -> bool:
        """Check whether one scalar statement can act on several groups of wires."""
        return False

    def qubit_operands(self, stmt: ir.Statement) -> tuple[ir.SSAValue, ...]:
        """Return the qubit-list operands of the squin statement `stmt`."""
        return tuple(getattr(stmt, name) for name in self.qubits)

    def param_operands(self, stmt: ir.Statement) -> tuple[ir.SSAValue, ...]:
        """Return the classical operands of the squin statement `stmt`."""
        return tuple(getattr(stmt, name) for name in self.params)

    def result_values(self, stmt: ir.Statement) -> tuple[ir.ResultValue, ...]:
        """Return the classical results of the squin statement `stmt`."""
        return tuple(getattr(stmt, name) for name in self.results)

    def adjoint(self, stmt: ir.Statement) -> bool:
        """Return the value of the attribute `adjoint` of the squin statement `stmt`."""
        return self.has_adjoint and getattr(stmt, "adjoint")

    def build(
        self,
        qubits: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...],
        adjoint: bool = False,
    ) -> ir.Statement:
        """Build the squin statement on the qubit lists `qubits`."""
        fields: dict[str, ir.SSAValue | bool] = {
            **dict(zip(self.qubits, qubits)),
            **dict(zip(self.params, params)),
        }
        if self.has_adjoint:
            fields["adjoint"] = adjoint
        return cast(Callable[..., ir.Statement], self.source)(**fields)


@dataclass(frozen=True)
class KindEntry(BaseEntry):
    """Map a squin gate or noise channel to the wire statement of the kind `kind`."""

    kind: Kind

    @property
    def counts(self) -> tuple[int, int]:
        """Return the number of qubits and parameters of the kind."""
        return self.kind.qubit_count, self.kind.param_count

    @property
    def broadcast(self) -> bool:
        """Return True, because `Gate` and `Noise` act on several groups at once."""
        return True

    @property
    def truncates(self) -> bool:
        """Check whether the register form of the kind stops at the shortest register."""
        return self.kind.truncates


@dataclass(frozen=True)
class GateEntry(KindEntry):
    """Map a squin gate to the wire gate of the kind `kind`."""

    kind: GateKind

    def scalar(
        self,
        wires: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...],
        adjoint: bool,
    ) -> Operation:
        """Return the gate on one wire per qubit list."""
        return Gate(self.kind, wires, params, adjoint=adjoint)

    def register(
        self,
        registers: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...],
        adjoint: bool,
    ) -> RegisterOperation:
        """Return the gate on one register per qubit list."""
        return RegisterGate(self.kind, registers, params, adjoint=adjoint)


@dataclass(frozen=True)
class NoiseEntry(KindEntry):
    """Map a squin noise channel to the wire channel of the kind `kind`."""

    kind: NoiseKind

    def scalar(
        self,
        wires: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...],
        adjoint: bool,
    ) -> Operation:
        """Return the channel on one wire per qubit list."""
        return Noise(self.kind, wires, params)

    def register(
        self,
        registers: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...],
        adjoint: bool,
    ) -> RegisterOperation:
        """Return the channel on one register per qubit list."""
        return RegisterNoise(self.kind, registers, params)


@dataclass(frozen=True)
class MeasureEntry(BaseEntry):
    """Map the squin measurement to `Measure` and `RegisterMeasure`."""

    @property
    def counts(self) -> tuple[int, int]:
        """Return 1 qubit and no parameters for a measurement."""
        return 1, 0

    def scalar(
        self,
        wires: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...],
        adjoint: bool,
    ) -> Operation:
        """Return the measurement of one wire."""
        (wire,) = wires
        return Measure(wire)

    def register(
        self,
        registers: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...],
        adjoint: bool,
    ) -> RegisterOperation:
        """Return the measurement of one register."""
        (register,) = registers
        return RegisterMeasure(register)


@dataclass(frozen=True)
class ResetEntry(BaseEntry):
    """Map the squin reset to `Reset` and `RegisterReset`."""

    @property
    def counts(self) -> tuple[int, int]:
        """Return 1 qubit and no parameters for a reset."""
        return 1, 0

    def scalar(
        self,
        wires: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...],
        adjoint: bool,
    ) -> Operation:
        """Return the reset of one wire."""
        (wire,) = wires
        return Reset(wire)

    def register(
        self,
        registers: tuple[ir.SSAValue, ...],
        params: tuple[ir.SSAValue, ...],
        adjoint: bool,
    ) -> RegisterOperation:
        """Return the reset of one register."""
        (register,) = registers
        return RegisterReset(register)


Entry: TypeAlias = GateEntry | NoiseEntry | MeasureEntry | ResetEntry
"""Map one squin statement on qubits to its wire statements."""

GATES = (
    GateEntry(gate_stmts.X, GateKind.X),
    GateEntry(gate_stmts.Y, GateKind.Y),
    GateEntry(gate_stmts.Z, GateKind.Z),
    GateEntry(gate_stmts.H, GateKind.H),
    GateEntry(gate_stmts.T, GateKind.T),
    GateEntry(gate_stmts.S, GateKind.S),
    GateEntry(gate_stmts.SqrtX, GateKind.SQRT_X),
    GateEntry(gate_stmts.SqrtY, GateKind.SQRT_Y),
    GateEntry(gate_stmts.Rx, GateKind.RX),
    GateEntry(gate_stmts.Ry, GateKind.RY),
    GateEntry(gate_stmts.Rz, GateKind.RZ),
    GateEntry(gate_stmts.CX, GateKind.CX),
    GateEntry(gate_stmts.CY, GateKind.CY),
    GateEntry(gate_stmts.CZ, GateKind.CZ),
    GateEntry(gate_stmts.CCZ, GateKind.CCZ),
    GateEntry(gate_stmts.Swap, GateKind.SWAP),
    GateEntry(gate_stmts.U3, GateKind.U3),
    GateEntry(gate_stmts.PhasedXZ, GateKind.PHASED_XZ),
    GateEntry(native_stmts.CZ, GateKind.NATIVE_CZ),
    GateEntry(native_stmts.R, GateKind.NATIVE_R),
    GateEntry(native_stmts.Rz, GateKind.NATIVE_RZ),
)
"""Map each squin and native gate to its wire gate."""

NOISES = (
    NoiseEntry(
        noise_stmts.SingleQubitPauliChannel, NoiseKind.SINGLE_QUBIT_PAULI_CHANNEL
    ),
    NoiseEntry(noise_stmts.TwoQubitPauliChannel, NoiseKind.TWO_QUBIT_PAULI_CHANNEL),
    NoiseEntry(noise_stmts.Depolarize, NoiseKind.DEPOLARIZE),
    NoiseEntry(noise_stmts.Depolarize2, NoiseKind.DEPOLARIZE2),
    NoiseEntry(noise_stmts.QubitLoss, NoiseKind.QUBIT_LOSS),
    NoiseEntry(noise_stmts.QubitLeakage, NoiseKind.QUBIT_LEAKAGE),
)
"""Map each squin noise channel on flat qubit lists to its wire channel.

`CorrelatedQubitLoss` takes nested qubit lists and has no entry.
"""

MEASURE = MeasureEntry(qubit_stmts.Measure)
RESET = ResetEntry(qubit_stmts.Reset)


def check(entry: Entry) -> Entry:
    """Return `entry` after a check against the schema of its squin statement.

    Each qubit-list field must hold a flat list of qubits. The number of qubit-list
    fields and classical fields must match the counts of the kind.
    """
    name = entry.source.__name__
    if not all(
        isinstance(typ, types.Generic)
        and is_subtype(typ, ilist.IListType)
        and is_subtype(typ.vars[0], QubitType)
        for typ in (entry.arguments[field] for field in entry.qubits)
    ):
        raise ValueError(f"The wire entry of {name} must take flat qubit lists.")
    if (len(entry.qubits), len(entry.params)) != entry.counts:
        raise ValueError(f"The wire entry of {name} must match the counts of its kind.")
    return entry


ENTRIES: dict[type[ir.Statement], Entry] = {
    entry.source: check(entry) for entry in (*GATES, *NOISES, MEASURE, RESET)
}
"""Map each squin statement class to its entry."""

GATE_ENTRIES: dict[GateKind, GateEntry] = {entry.kind: entry for entry in GATES}
"""Map each gate kind back to the squin statement that it copies."""

NOISE_ENTRIES: dict[NoiseKind, NoiseEntry] = {entry.kind: entry for entry in NOISES}
"""Map each noise kind back to the squin statement that it copies."""


def entry_of(stmt: Operation) -> Entry:
    """Return the entry of the squin statement that the wire statement `stmt` copies."""
    if isinstance(stmt, (Gate, RegisterGate)):
        return GATE_ENTRIES[stmt.kind]
    if isinstance(stmt, (Noise, RegisterNoise)):
        return NOISE_ENTRIES[stmt.kind]
    if isinstance(stmt, (Measure, RegisterMeasure)):
        return MEASURE
    if isinstance(stmt, (Reset, RegisterReset)):
        return RESET
    raise ValueError(f"The wire operation '{stmt.name}' has no squin entry.")
