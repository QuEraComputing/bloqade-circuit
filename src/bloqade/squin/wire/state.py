"""Define wire allocation, register transfer, measurement and reset statements."""

from kirin import ir, types
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import MeasurementResultType

from .types import WireType, RegisterType
from .traits import Threads
from .operations import Operation, RegisterOperation

dialect = ir.Dialect("squin.wire.state")


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
    """Allocate `size` qubits in the zero state and return them as one register.

    The caller must supply a nonnegative size.
    """

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
