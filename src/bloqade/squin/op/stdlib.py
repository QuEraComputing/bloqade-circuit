from ast import AST, Call
from typing import overload
from dataclasses import dataclass

from kirin import ir, lowering
from kirin.decl import statement
from kirin.prelude import structural_no_opt

from bloqade.types import Qubit

from . import stmts, types
from .. import qubit
from ._dialect import dialect
from ._wrapper import x, y, z, rot, phase, control


@ir.dialect_group(structural_no_opt.add(dialect))
def op(self):
    def run_pass(method):
        pass

    return run_pass


@op
def rx(theta: float) -> types.Op:
    """Rotation X gate."""
    return rot(x(), theta)


@op
def ry(theta: float) -> types.Op:
    """Rotation Y gate."""
    return rot(y(), theta)


@op
def rz(theta: float) -> types.Op:
    """Rotation Z gate."""
    return rot(z(), theta)


@op
def cphase(theta: float) -> types.Op:
    """Control Phase gate."""
    return control(phase(theta), n_controls=1)


@dataclass(frozen=True)
class SingleQubitControlLowering(lowering.FromPythonCall):
    target_gate_name: str

    def lower(
        self, stmt: type["SingleQubitControl"], state: lowering.State[AST], node: Call
    ):
        op_ = state.current_frame.push(getattr(stmts, self.target_gate_name)())
        ctrl = state.current_frame.push(stmts.Control(op_.result, n_controls=1))

        if len(node.args) == 0:
            return ctrl

        if len(node.keywords) != 0:
            raise NotImplementedError("Named arguments for controls not yet supported!")

        qubits = [state.lower(qbit).expect_one() for qbit in node.args]
        return state.current_frame.push(qubit.ApplyAny(ctrl.result, tuple(qubits)))


@statement
class SingleQubitControl(ir.Statement):
    pass


@statement(dialect=dialect)
class ControlX(SingleQubitControl):
    traits = frozenset({SingleQubitControlLowering("X")})


@statement(dialect=dialect)
class ControlY(SingleQubitControl):
    traits = frozenset({SingleQubitControlLowering("Y")})


@statement(dialect=dialect)
class ControlZ(SingleQubitControl):
    traits = frozenset({SingleQubitControlLowering("Z")})


@statement(dialect=dialect)
class ControlH(SingleQubitControl):
    traits = frozenset({SingleQubitControlLowering("H")})


@overload
def cx() -> types.Op:
    """Controlled X gate."""
    ...


@overload
def cx(ctrl: Qubit, target: Qubit) -> None:
    """Apply a controlled X gate to control and target"""
    ...


@lowering.wraps(ControlX)
def cx(*args: Qubit) -> types.Op | None: ...


@overload
def cy() -> types.Op:
    """Controlled X gate."""
    ...


@overload
def cy(ctrl: Qubit, target: Qubit) -> None:
    """Apply a controlled X gate to control and target"""
    ...


@lowering.wraps(ControlY)
def cy(*args: Qubit) -> types.Op | None: ...


@overload
def cz() -> types.Op:
    """Controlled X gate."""
    ...


@overload
def cz(ctrl: Qubit, target: Qubit) -> None:
    """Apply a controlled X gate to control and target"""
    ...


@lowering.wraps(ControlZ)
def cz(*args: Qubit) -> types.Op | None: ...


@overload
def ch() -> types.Op:
    """Controlled X gate."""
    ...


@overload
def ch(ctrl: Qubit, target: Qubit) -> None:
    """Apply a controlled X gate to control and target"""
    ...


@lowering.wraps(ControlX)
def ch(*args: Qubit) -> types.Op | None: ...
