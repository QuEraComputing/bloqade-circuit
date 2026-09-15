"""Define the jeff statements that act on qubits and qubit registers.

Each statement mirrors one jeff qubit or qureg operation.
"""

from kirin import ir, types
from kirin.decl import info, statement

from bloqade.jeff.types import WireType, QuregType, is_subtype, qureg_length
from bloqade.jeff.constants import const_int

dialect = ir.Dialect("jeff.wire")


def _register_length(reg: ir.SSAValue) -> int | None:
    """Return the length of a register, or None if the length is unknown.

    The method reads the register type first. If the type has no length, the
    method reads a constant allocation size or the number of wires in a
    `RegCreate`. It follows `Extract` and `Insert` back to the register they
    take, because both keep the register length.
    """
    while True:
        if (length := qureg_length(reg.type)) is not None:
            return length
        owner = reg.owner
        if isinstance(owner, RegAlloc):
            return const_int(owner.size)
        if isinstance(owner, RegCreate):
            return len(owner.wires)
        if isinstance(owner, (Extract, Insert)):
            reg = owner.reg
            continue
        return None


def _within(stmt: ir.Statement, reg: ir.SSAValue, index: ir.SSAValue) -> None:
    """Raise a type error if a constant index is outside the register.

    A negative constant index is always outside. The upper bound applies when the
    register length is known.
    """
    slot = const_int(index)
    if slot is None:
        return
    length = _register_length(reg)
    if slot < 0 or (length is not None and slot >= length):
        size = "a register" if length is None else f"a register of {length} qubits"
        raise ir.TypeCheckError(stmt, f"slot {slot} is outside {size}")


def _keeps_length(stmt: ir.Statement, reg: ir.SSAValue, result: ir.SSAValue) -> None:
    """Raise a type error if a result register type claims another length."""
    before, after = qureg_length(reg.type), qureg_length(result.type)
    if before is not None and after is not None and before != after:
        raise ir.TypeCheckError(
            stmt, f"a register of {before} qubits comes out typed qureg[{after}]"
        )


@statement(dialect=dialect)
class Alloc(ir.Statement):
    """Allocate a qubit in the |0> state and return its first wire."""

    result: ir.ResultValue = info.result(WireType)


@statement(dialect=dialect)
class Free(ir.Statement):
    """Release a qubit and consume its final wire."""

    wire: ir.SSAValue = info.argument(WireType)


@statement(dialect=dialect)
class FreeZero(ir.Statement):
    """Release a qubit that is in the |0> state and consume its final wire.

    If the qubit is in any other state, the behavior is undefined.
    """

    name = "free_zero"

    wire: ir.SSAValue = info.argument(WireType)


@statement(dialect=dialect)
class Reset(ir.Statement):
    """Reset a qubit to the |0> state and return its next wire."""

    wire: ir.SSAValue = info.argument(WireType)
    result: ir.ResultValue = info.result(WireType)


@statement(dialect=dialect)
class MeasureNd(ir.Statement):
    """Measure a qubit in the Z basis and keep the qubit.

    The statement returns the next wire of the qubit and the measured bit.
    """

    name = "measure_nd"
    wire: ir.SSAValue = info.argument(WireType)
    result_wire: ir.ResultValue = info.result(WireType)
    bit: ir.ResultValue = info.result(types.Bool)


@statement(dialect=dialect)
class Measure(ir.Statement):
    """Measure a qubit in the Z basis and consume its final wire."""

    wire: ir.SSAValue = info.argument(WireType)
    bit: ir.ResultValue = info.result(types.Bool)


@statement(dialect=dialect, init=False)
class RegCreate(ir.Statement):
    """Create a qubit register from individual wires."""

    name = "reg_create"
    wires: tuple[ir.SSAValue, ...] = info.argument(WireType)
    result: ir.ResultValue = info.result(QuregType)

    def __init__(self, wires: tuple[ir.SSAValue, ...]) -> None:
        """Build a statement that creates a register with one slot per wire."""
        super().__init__(
            args=wires,
            result_types=(QuregType,),
            args_slice={"wires": slice(0, None)},
        )

    def verify_type(self) -> None:
        """Check the operand types and that a typed length equals the wire count."""
        super().verify_type()
        typed = qureg_length(self.result.type)
        if typed not in (None, len(self.wires)):
            raise ir.TypeCheckError(
                self, f"a register of {len(self.wires)} qubits is typed qureg[{typed}]"
            )


@statement(dialect=dialect)
class RegAlloc(ir.Statement):
    """Allocate a register of `size` qubits, all in the |0> state."""

    name = "reg_alloc"

    size: ir.SSAValue = info.argument(types.Int)
    result: ir.ResultValue = info.result(QuregType)

    def verify(self) -> None:
        """Check that a constant size is zero or positive."""
        super().verify()
        size = const_int(self.size)
        if size is not None and size < 0:
            raise ir.ValidationError(self, f"a register of {size} qubits")

    def verify_type(self) -> None:
        """Check the operand types and that a typed length equals a constant size."""
        super().verify_type()
        size = const_int(self.size)
        typed = qureg_length(self.result.type)
        if size is not None and typed not in (None, size):
            raise ir.TypeCheckError(
                self, f"a register of {size} qubits is typed qureg[{typed}]"
            )


@statement(dialect=dialect)
class RegFree(ir.Statement):
    """Release a qubit register and consume the register value."""

    name = "reg_free"
    reg: ir.SSAValue = info.argument(QuregType)


@statement(dialect=dialect)
class RegFreeZero(ir.Statement):
    """Release a register whose qubits are all in the |0> state.

    If any qubit is in another state, the behavior is undefined.
    """

    name = "reg_free_zero"

    reg: ir.SSAValue = info.argument(QuregType)


def _same_register(reg: ir.SSAValue) -> types.TypeAttribute:
    """Return the register type of `reg`, so that a static length survives an extract.

    The same holds for an insert. If `reg` does not have a register type yet, the
    result is a register of unknown length.
    """
    return reg.type if is_subtype(reg.type, QuregType) else QuregType


@statement(dialect=dialect)
class Extract(ir.Statement):
    """Extract the qubit at an index and leave that slot empty."""

    reg: ir.SSAValue = info.argument(QuregType)
    index: ir.SSAValue = info.argument(types.Int)
    result_reg: ir.ResultValue = info.result(QuregType)
    wire: ir.ResultValue = info.result(WireType)

    def __init__(self, reg: ir.SSAValue, index: ir.SSAValue) -> None:
        """Build a statement that takes the wire at `index` out of `reg`."""
        super().__init__(
            args=(reg, index),
            result_types=(_same_register(reg), WireType),
            args_slice={"reg": 0, "index": 1},
        )

    def verify_type(self) -> None:
        """Check the operand types and that a constant index fits the register."""
        super().verify_type()
        _within(self, self.reg, self.index)
        _keeps_length(self, self.reg, self.result_reg)


@statement(dialect=dialect)
class Insert(ir.Statement):
    """Insert a qubit into the empty slot at an index."""

    reg: ir.SSAValue = info.argument(QuregType)
    index: ir.SSAValue = info.argument(types.Int)
    wire: ir.SSAValue = info.argument(WireType)
    result: ir.ResultValue = info.result(QuregType)

    def __init__(self, reg: ir.SSAValue, index: ir.SSAValue, wire: ir.SSAValue) -> None:
        """Build a statement that puts `wire` into the empty slot `index` of `reg`."""
        super().__init__(
            args=(reg, index, wire),
            result_types=(_same_register(reg),),
            args_slice={"reg": 0, "index": 1, "wire": 2},
        )

    def verify_type(self) -> None:
        """Check the operand types and that a constant index fits the register."""
        super().verify_type()
        _within(self, self.reg, self.index)
        _keeps_length(self, self.reg, self.result)


@statement(dialect=dialect)
class ExtractSlice(ir.Statement):
    """Extract `length` qubits starting at `start` into a new register.

    The statement leaves those slots of the source register empty.
    """

    name = "extract_slice"

    reg: ir.SSAValue = info.argument(QuregType)
    start: ir.SSAValue = info.argument(types.Int)
    length: ir.SSAValue = info.argument(types.Int)
    result_reg: ir.ResultValue = info.result(QuregType)
    slice_reg: ir.ResultValue = info.result(QuregType)


@statement(dialect=dialect)
class InsertSlice(ir.Statement):
    """Insert a register into empty slots of another register, starting at `start`."""

    name = "insert_slice"

    reg: ir.SSAValue = info.argument(QuregType)
    start: ir.SSAValue = info.argument(types.Int)
    slice_reg: ir.SSAValue = info.argument(QuregType)
    result: ir.ResultValue = info.result(QuregType)


@statement(dialect=dialect)
class RegSplit(ir.Statement):
    """Split a register in two at an index."""

    name = "reg_split"

    reg: ir.SSAValue = info.argument(QuregType)
    index: ir.SSAValue = info.argument(types.Int)
    before: ir.ResultValue = info.result(QuregType)
    after: ir.ResultValue = info.result(QuregType)


@statement(dialect=dialect)
class RegJoin(ir.Statement):
    """Join two registers into one."""

    name = "reg_join"

    first: ir.SSAValue = info.argument(QuregType)
    second: ir.SSAValue = info.argument(QuregType)
    result: ir.ResultValue = info.result(QuregType)


@statement(dialect=dialect)
class RegLength(ir.Statement):
    """Return the number of qubits in a register.

    The statement also returns the register, because a register is linear.
    """

    name = "reg_length"

    reg: ir.SSAValue = info.argument(QuregType)
    result_reg: ir.ResultValue = info.result(QuregType)
    length: ir.ResultValue = info.result(types.Int)
