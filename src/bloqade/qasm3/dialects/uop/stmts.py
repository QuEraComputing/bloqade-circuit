from kirin import ir, lowering
from kirin.decl import info, statement

from bloqade.qasm3.types import QubitType
from bloqade.qasm3.dialects.expr.stmts import PyNum

from ._dialect import dialect


# Base classes (not registered to a dialect)

@statement
class SingleQubitGate(ir.Statement):
    """Base class for single qubit gates."""

    traits = frozenset({lowering.FromPythonCall()})
    qarg: ir.SSAValue = info.argument(QubitType)
    """qarg (Qubit): The qubit argument."""


@statement
class RotationGate(SingleQubitGate):
    """Base class for single-qubit rotation gates."""

    theta: ir.SSAValue = info.argument(PyNum)
    """theta (float): The rotation angle."""


@statement
class TwoQubitCtrlGate(ir.Statement):
    """Base class for two-qubit controlled gates."""

    traits = frozenset({lowering.FromPythonCall()})
    ctrl: ir.SSAValue = info.argument(QubitType)
    """ctrl (Qubit): The control qubit."""
    qarg: ir.SSAValue = info.argument(QubitType)
    """qarg (Qubit): The target qubit."""


# Single-qubit gates

@statement(dialect=dialect)
class H(SingleQubitGate):
    """Apply the Hadamard gate."""
    name = "h"


@statement(dialect=dialect)
class X(SingleQubitGate):
    """Apply the X gate."""
    name = "x"


@statement(dialect=dialect)
class Y(SingleQubitGate):
    """Apply the Y gate."""
    name = "y"


@statement(dialect=dialect)
class Z(SingleQubitGate):
    """Apply the Z gate."""
    name = "z"


@statement(dialect=dialect)
class S(SingleQubitGate):
    """Apply the S gate."""
    name = "s"


@statement(dialect=dialect)
class T(SingleQubitGate):
    """Apply the T gate."""
    name = "t"


# Rotation gates

@statement(dialect=dialect)
class RX(RotationGate):
    """Apply the RX gate."""
    name = "rx"


@statement(dialect=dialect)
class RY(RotationGate):
    """Apply the RY gate."""
    name = "ry"


@statement(dialect=dialect)
class RZ(RotationGate):
    """Apply the RZ gate."""
    name = "rz"


# Two-qubit controlled gates

@statement(dialect=dialect)
class CX(TwoQubitCtrlGate):
    """Apply the CNOT (CX) gate."""
    name = "cx"


@statement(dialect=dialect)
class CY(TwoQubitCtrlGate):
    """Apply the Controlled-Y gate."""
    name = "cy"


@statement(dialect=dialect)
class CZ(TwoQubitCtrlGate):
    """Apply the Controlled-Z gate."""
    name = "cz"


# General unitary gate

@statement(dialect=dialect)
class UGate(SingleQubitGate):
    """Apply a general single qubit unitary gate U(theta, phi, lam)."""
    name = "U"
    theta: ir.SSAValue = info.argument(PyNum)
    """theta (float): The theta parameter."""
    phi: ir.SSAValue = info.argument(PyNum)
    """phi (float): The phi parameter."""
    lam: ir.SSAValue = info.argument(PyNum)
    """lam (float): The lambda parameter."""
