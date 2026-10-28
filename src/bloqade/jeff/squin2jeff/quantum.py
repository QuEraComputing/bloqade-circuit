"""This module holds the rules that emit jeff gates, allocations and measurements."""

# The squin gate statements and the kirin `py` statements derive from base classes
# that a bare `@statement` decorates, which pyright reads as functions. A rule that
# stacks `interp.impl` for several of them then fails the argument check.
# pyright: reportArgumentType=false

from kirin import ir, interp

from bloqade.qubit import stmts as qubit_stmts
from bloqade.jeff.forms import GATES
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.jeff.dialects import stmts

from .linearize import KEY, Frame, Value, Linearize


@gate_stmts.dialect.register(key=KEY)
class _Gates(interp.MethodTable):
    """A method table that emits one jeff gate per qubit, or group, of a squin gate."""

    @interp.impl(gate_stmts.X)
    @interp.impl(gate_stmts.Y)
    @interp.impl(gate_stmts.Z)
    @interp.impl(gate_stmts.H)
    @interp.impl(gate_stmts.S)
    @interp.impl(gate_stmts.T)
    @interp.impl(gate_stmts.SqrtX)
    @interp.impl(gate_stmts.SqrtY)
    @interp.impl(gate_stmts.Rx)
    @interp.impl(gate_stmts.Ry)
    @interp.impl(gate_stmts.Rz)
    @interp.impl(gate_stmts.U3)
    @interp.impl(gate_stmts.CX)
    @interp.impl(gate_stmts.CY)
    @interp.impl(gate_stmts.CZ)
    @interp.impl(gate_stmts.CCZ)
    @interp.impl(gate_stmts.Swap)
    def gate(
        self, emit: Linearize, frame: Frame, stmt: ir.Statement
    ) -> interp.StatementResult[Value]:
        """Emit the gate with its angles in radians, since squin gives turns."""
        form = GATES[type(stmt)]
        angles = [emit.radians(frame, a) for a in stmt.args[: form.angles]]
        adjoint = isinstance(
            stmt, (gate_stmts.S, gate_stmts.T, gate_stmts.SqrtX, gate_stmts.SqrtY)
        ) and bool(stmt.adjoint)
        emit.gate(frame, form, stmt.args[form.angles :], angles, adjoint)
        return ()


@qubit_stmts.dialect.register(key=KEY)
class _Qubits(interp.MethodTable):
    """A method table that emits allocation, reset and measurement."""

    @interp.impl(qubit_stmts.New)
    def new(
        self, emit: Linearize, frame: Frame, stmt: qubit_stmts.New
    ) -> interp.StatementResult[Value]:
        """Allocate a wire and make it the wire of the new root."""
        frame.wires[stmt.result] = frame.push(stmts.Alloc()).result
        return (None,)

    @interp.impl(qubit_stmts.Reset)
    def reset(
        self, emit: Linearize, frame: Frame, stmt: qubit_stmts.Reset
    ) -> interp.StatementResult[Value]:
        """Reset each qubit of the list."""
        emit.reset_qubits(frame, stmt.qubits)
        return ()

    @interp.impl(qubit_stmts.Measure)
    def measure(
        self, emit: Linearize, frame: Frame, stmt: qubit_stmts.Measure
    ) -> interp.StatementResult[Value]:
        """Measure and keep each qubit of the list, and return the bits."""
        return (emit.measure(frame, stmt.qubits),)

    @interp.impl(qubit_stmts.IsOne)
    def is_one(
        self, emit: Linearize, frame: Frame, stmt: qubit_stmts.IsOne
    ) -> interp.StatementResult[Value]:
        """Return the bits, because a jeff bit is one exactly when the qubit was."""
        return (frame.value(stmt.measurements),)

    @interp.impl(qubit_stmts.IsZero)
    def is_zero(
        self, emit: Linearize, frame: Frame, stmt: qubit_stmts.IsZero
    ) -> interp.StatementResult[Value]:
        """Return the negated bits."""
        return (emit.negate(frame, stmt.measurements),)
