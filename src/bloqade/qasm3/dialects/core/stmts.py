from kirin import ir, types, lowering
from kirin.decl import info, statement

from bloqade.qasm3.types import BitType, BitRegType, QRegType, QubitType

from ._dialect import dialect


@statement(dialect=dialect)
class Barrier(ir.Statement):
    """Barrier synchronization across a set of qubits."""

    name = "barrier"
    traits = frozenset({lowering.FromPythonCall()})
    qargs: tuple[ir.SSAValue, ...] = info.argument(QubitType)
    """qargs (Qubit...): The qubits to synchronize."""


@statement(dialect=dialect)
class QRegNew(ir.Statement):
    """Create a new quantum register."""

    name = "qreg.new"
    traits = frozenset({lowering.FromPythonCall()})
    n_qubits: ir.SSAValue = info.argument(types.Int)
    """n_qubits: The number of qubits in the register."""
    result: ir.ResultValue = info.result(QRegType)
    """A new quantum register with n_qubits set to |0>."""


@statement(dialect=dialect)
class BitRegNew(ir.Statement):
    """Create a new classical bit register."""

    name = "bitreg.new"
    traits = frozenset({lowering.FromPythonCall()})
    n_bits: ir.SSAValue = info.argument(types.Int)
    """n_bits (Int): The number of bits in the register."""
    result: ir.ResultValue = info.result(BitRegType)
    """result (BitReg): The new bit register with all bits set to 0."""


@statement(dialect=dialect)
class QRegGet(ir.Statement):
    """Get a qubit from a quantum register."""

    name = "qreg.get"
    traits = frozenset({lowering.FromPythonCall(), ir.Pure()})
    reg: ir.SSAValue = info.argument(QRegType)
    """reg (QReg): The quantum register."""
    idx: ir.SSAValue = info.argument(types.Int)
    """idx (Int): The index of the qubit in the register."""
    result: ir.ResultValue = info.result(QubitType)
    """result (Qubit): The qubit at position `idx`."""


@statement(dialect=dialect)
class BitRegGet(ir.Statement):
    """Get a bit from a classical bit register."""

    name = "bitreg.get"
    traits = frozenset({lowering.FromPythonCall(), ir.Pure()})
    reg: ir.SSAValue = info.argument(BitRegType)
    """reg (BitReg): The classical bit register."""
    idx: ir.SSAValue = info.argument(types.Int)
    """idx (Int): The index of the bit in the register."""
    result: ir.ResultValue = info.result(BitType)
    """result (Bit): The bit at position `idx`."""


@statement(dialect=dialect)
class Measure(ir.Statement):
    """Measure a qubit (or register) and store the result in a bit (or register)."""

    name = "measure"
    traits = frozenset({lowering.FromPythonCall()})
    qarg: ir.SSAValue = info.argument(QubitType | QRegType)
    """qarg (Qubit | QReg): The qubit or quantum register to measure."""
    carg: ir.SSAValue = info.argument(BitType | CRegType)
    """carg (Bit | CReg): The bit or register to store the result in."""


@statement(dialect=dialect)
class Reset(ir.Statement):
    """Reset a qubit to the |0> state."""

    name = "reset"
    traits = frozenset({lowering.FromPythonCall()})
    qarg: ir.SSAValue = info.argument(QubitType)
    """qarg (Qubit): The qubit to reset."""
