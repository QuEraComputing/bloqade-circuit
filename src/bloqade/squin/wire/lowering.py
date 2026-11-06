"""Use Kirin's Python lowering interface to emit validated wire operations."""

import ast
import inspect
from types import FunctionType
from typing import Never, TypeVar, ParamSpec, cast
from collections.abc import Callable

from kirin import ir, types, lowering
from kirin.dialects import py, scf, func
from kirin.dialects.lowering import call as call_lowering, func as func_lowering
from kirin.dialects.scf.lowering import Lowering as StructuredLowering

from bloqade import squin
from bloqade.squin.wire import GateKind, RegisterType, stmts, kernel
from bloqade.squin.wire.typeinfer import InferWireTypes
from bloqade.squin.analysis.validation.wire import WireValidation

KEY = "lowering.squin_wire"
Param = ParamSpec("Param")
Return = TypeVar("Return")


def reject(node: ast.AST) -> Never:
    """Report syntax that the direct wire prototype cannot lower."""
    raise lowering.BuildError(
        f"The direct wire prototype does not support {ast.unparse(node)!r}."
    )


def registers(frame: lowering.Frame[ast.AST]) -> dict[str, ir.SSAValue]:
    """Return the current register bindings of a Kirin lowering frame."""
    return {
        name: value
        for name, value in frame.defs.items()
        if value.type.is_subseteq(RegisterType)
    }


def bind(frame: lowering.Frame[ast.AST], name: str, value: ir.SSAValue) -> None:
    """Update the binding that Kirin's loop lowering captures and yields."""
    value.name = name
    frame.defs[name] = value


@py.assign.dialect.register(key=KEY)
class Assignments(lowering.FromPythonAST):
    """Bind each allocation to one register name at function scope."""

    def lower_Assign(self, state: lowering.State[ast.AST], node: ast.Assign) -> None:
        """Lower a register allocation through Kirin's call dispatch."""
        frame = state.current_frame
        if not (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and state.get_global(node.value.func).data is squin.qalloc
            and frame.parent is not None
            and frame.parent.parent is None
            and frame.get_local(node.targets[0].id) is None
        ):
            reject(node)
        value = state.lower(node.value).expect_one()
        bind(frame, node.targets[0].id, value)


@call_lowering.dialect.register(key=KEY)
class Calls(lowering.FromPythonAST):
    """Replace supported squin calls with wire allocation, gates and measurement."""

    def lower_Call_global_method(
        self, state: lowering.State[ast.AST], method: ir.Method, node: ast.Call
    ) -> lowering.Result:
        """Select a wire operation using the callable that Kirin resolves."""
        frame = state.current_frame
        if node.keywords:
            reject(node)
        if method is squin.qalloc and len(node.args) == 1:
            size = state.lower(node.args[0]).expect_one()
            return frame.push(stmts.AllocRegister(size))
        if method is squin.broadcast.measure and len(node.args) == 1:
            name, value = self.register(state, node.args[0])
            measured = frame.push(stmts.RegisterMeasure(value))
            bind(frame, name, measured.register_out)
            return measured.bits
        kind = {squin.h: GateKind.H, squin.x: GateKind.X, squin.cx: GateKind.CX}.get(
            method
        )
        if kind is None or len(node.args) != kind.qubit_count:
            reject(node)
        borrowed: list[tuple[str, ir.SSAValue, ir.SSAValue]] = []
        for operand in node.args:
            if not isinstance(operand, ast.Subscript):
                reject(operand)
            name, value = self.register(state, operand.value)
            index = state.lower(operand.slice).expect_one()
            taken = frame.push(stmts.Borrow(value, index))
            bind(frame, name, taken.register_out)
            borrowed.append((name, index, taken.wire))
        gate = frame.push(stmts.Gate(kind, tuple(wire for _, _, wire in borrowed)))
        for (name, index, _), wire in zip(borrowed, gate.results, strict=True):
            released = frame.push(stmts.Release(frame.defs[name], index, wire))
            bind(frame, name, released.register_out)

    def register(
        self, state: lowering.State[ast.AST], node: ast.expr
    ) -> tuple[str, ir.SSAValue]:
        """Read a named register through Kirin's frame capture mechanism."""
        if not isinstance(node, ast.Name):
            reject(node)
        value = state.lower(node).expect_one()
        if not value.type.is_subseteq(RegisterType):
            reject(node)
        return node.id, value


@scf.dialect.register(key=KEY)
class ControlFlow(StructuredLowering):
    """Use Kirin's counted-loop lowering with updated register bindings."""

    def lower_For(
        self, state: lowering.State[ast.AST], node: ast.For
    ) -> lowering.Result:
        """Let Kirin capture registers and yield their current values on each iteration."""
        if not (
            isinstance(node.target, ast.Name)
            and isinstance(node.iter, ast.Call)
            and state.get_global(node.iter.func).data is range
            and not node.orelse
            and state.current_frame.get_local(node.target.id) is None
        ):
            reject(node)
        return super().lower_For(state, node)

    def lower_If(self, state: lowering.State[ast.AST], node: ast.If) -> Never:
        """Reject branches in the direct wire prototype."""
        reject(node)

    def lower_IfExp(self, state: lowering.State[ast.AST], node: ast.IfExp) -> Never:
        """Reject conditional expressions in the direct wire prototype."""
        reject(node)


@func_lowering.dialect.register(key=KEY)
class Functions(func_lowering.Lowering):
    """Use Kirin's function lowering and free local registers before returning."""

    def lower_FunctionDef(
        self, state: lowering.State[ast.AST], node: ast.FunctionDef
    ) -> lowering.Result:
        """Lower a top-level function with integer parameters and one final return."""
        arguments = node.args
        if (
            state.current_frame.parent is not None
            or arguments.vararg
            or arguments.kwarg
            or arguments.defaults
            or arguments.kwonlyargs
            or arguments.posonlyargs
            or any(
                self.get_hint(state, arg.annotation) != types.Int
                for arg in arguments.args
            )
            or any(isinstance(statement, ast.Return) for statement in node.body[:-1])
        ):
            reject(node)
        if not node.body or not isinstance(node.body[-1], ast.Return):
            node.body.append(ast.copy_location(ast.Return(value=None), node))
        return super().lower_FunctionDef(state, node)

    def lower_Return(self, state: lowering.State[ast.AST], node: ast.Return) -> None:
        """Return the classical result after freeing every local register."""
        frame = state.current_frame
        result = (
            state.lower(node.value).expect_one()
            if node.value is not None
            else frame.push(func.ConstantNone()).result
        )
        for value in registers(frame).values():
            frame.push(stmts.FreeRegister(value))
        frame.push(func.Return(result))

    def lower_Lambda(self, state: lowering.State[ast.AST], node: ast.Lambda) -> Never:
        """Reject lambda expressions in the direct wire prototype."""
        reject(node)


driver = lowering.Python(kernel, keys=[KEY, "main", "default"])


def wire_kernel(function: Callable[Param, Return]) -> ir.Method[Param, Return]:
    """Run Kirin's Python lowering with the wire handlers, then infer and validate types."""
    _, start = inspect.getsourcelines(function)
    code = driver.python_function(cast(FunctionType, function), lineno_offset=start - 1)
    method = ir.Method(
        dialects=kernel,
        code=code,
        py_func=function,
        file=inspect.getfile(function),
        lineno_begin=start - 1,
    )
    InferWireTypes(kernel)(method)
    WireValidation().check(method)
    return method
