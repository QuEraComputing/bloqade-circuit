"""Emit wire operations while Kirin lowers individual Python expressions."""

from __future__ import annotations

import ast
import inspect
from types import FunctionType
from typing import cast
from weakref import WeakKeyDictionary
from dataclasses import field, dataclass

from kirin import ir, types, lowering
from kirin.passes import Fold
from kirin.rewrite import Walk, Fixpoint, DeadCodeElimination
from kirin.dialects import py, func, ilist

from bloqade.types import QubitType
from bloqade.constants import constant_int
from bloqade.squin.wire import kernel
from bloqade.squin.emit.wire import EmitWire, WireFrame
from bloqade.analysis.indices import IndexExpr
from bloqade.squin.wire.typeinfer import InferWireTypes
from bloqade.squin.emit.wire.values import (
    View,
    Qubit,
    Value,
    Element,
    Register,
    contains_location,
)
from bloqade.squin.rewrite.wire.tools import Retype
from bloqade.squin.emit.wire.functions import is_library
from bloqade.squin.rewrite.wire.signature import (
    Layout,
    packed_type,
    quantum_type,
    bounded_list_lengths,
)
from bloqade.squin.analysis.validation.wire import WireValidation

from .calls import invoke

KEY = "lowering.squin_wire"
SOURCES: WeakKeyDictionary[ir.Method, tuple[ir.Method, Layout]] = WeakKeyDictionary()


class ExpressionEmitter(EmitWire):
    """Resolve index arithmetic before the enclosing function exists."""

    def index(self, value: ir.SSAValue) -> IndexExpr:
        """Build an index expression from constants and integer arithmetic."""
        if value in self.indices.facts:
            return self.indices.facts[value]
        if value in self.lengths:
            return self.lengths[value]
        if (number := constant_int(value)) is not None:
            return IndexExpr(number)
        owner = value.owner
        if isinstance(owner, py.USub):
            return self.index(owner.args[0]).scale(-1)
        if isinstance(owner, py.assign.Alias):
            return self.index(owner.value)
        if isinstance(owner, (py.Add, py.Sub, py.Mult)):
            left, right = (self.index(arg) for arg in owner.args)
            if isinstance(owner, py.Add):
                return left + right
            if isinstance(owner, py.Sub):
                return left - right
            if left.constant is not None:
                return right.scale(left.constant)
            if right.constant is not None:
                return left.scale(right.constant)
        return super().index(value)


@dataclass
class Compiler:
    """Compile static callees once and retain their source calling conventions."""

    compiled: dict[ir.Method, ir.Method] = field(default_factory=dict)
    active: set[FunctionType] = field(default_factory=set)

    def compile(self, function: FunctionType) -> ir.Method:
        """Lower one Python function and validate its complete wire result."""
        if function in self.active:
            raise lowering.BuildError(
                "Wire lowering requires nonrecursive static calls."
            )
        self.active.add(function)
        try:
            driver = Python(self)
            _, start = inspect.getsourcelines(function)
            code = driver.python_function(function, lineno_offset=start - 1)
            for marker in driver.loop_markers:
                marker.drop_all_references()
            method = ir.Method(
                kernel,
                code,
                py_func=function,
                mod=inspect.getmodule(function),
                file=inspect.getfile(function),
                lineno_begin=start - 1,
            )
            Fixpoint(Walk(DeadCodeElimination())).rewrite(code)
            Fold(kernel).fixpoint(method)
            InferWireTypes(kernel)(method)
            Walk(Retype(bounded_list_lengths)).rewrite(code)
            WireValidation().check(method)
            assert isinstance(code, func.Function)
            outputs = (
                list(code.signature.output.vars)
                if driver.output_count > 1
                else [code.signature.output]
            )
            ordinary = packed_type(outputs[: driver.ordinary_count])
            if not ordinary.is_subseteq(driver.return_type):
                raise lowering.BuildError(
                    f"Function '{function.__name__}' returns {ordinary}, which does not match its annotation {driver.return_type}."
                )
            source_block = ir.Block(argtypes=(types.Any, *driver.input_types))
            source = ir.Method(
                kernel,
                func.Function(
                    sym_name=code.sym_name,
                    slots=code.slots,
                    signature=func.Signature(driver.input_types, ordinary),
                    body=ir.Region(source_block),
                ),
                py_func=function,
                mod=method.mod,
            )
            layout = Layout(
                tuple(
                    i
                    for i, typ in enumerate(driver.input_types)
                    if quantum_type(typ) is not None
                ),
                driver.ordinary_count,
                driver.ordinary_count > 1,
            )
            SOURCES[method] = source, layout
            return method
        finally:
            self.active.remove(function)

    def callee(self, method: ir.Method) -> tuple[ir.Method, ir.Method, Layout]:
        """Return the source signature and wire method of a static callee."""
        if method in SOURCES:
            source, layout = SOURCES[method]
            return source, method, layout
        if method not in self.compiled:
            if not isinstance(method.py_func, FunctionType):
                raise lowering.BuildError(
                    "A direct wire callee must retain its Python function."
                )
            self.compiled[method] = self.compile(method.py_func)
        wired = self.compiled[method]
        source, layout = SOURCES[wired]
        return source, wired, layout


class Python(lowering.Python):
    """Use Kirin's syntax handlers and emit each quantum expression immediately."""

    def __init__(self, compiler: Compiler) -> None:
        super().__init__(kernel, keys=[KEY, "main", "default"])
        self.compiler = compiler
        dummy = func.Function(
            sym_name="lowering",
            signature=func.Signature((), types.Any),
            body=ir.Region(ir.Block(argtypes=(types.Any,))),
        )
        self.emitter = ExpressionEmitter(kernel, ir.Method(kernel, dummy), {})
        self.emitter.reset()
        self.frames: dict[int, WireFrame] = {}
        self.frame_owners: list[lowering.Frame[ast.AST]] = []
        self.meanings: dict[ir.SSAValue, Value] = {}
        self.bindings = ir.Block()
        self.loop_markers: list[ir.Statement] = []
        self.done: set[ir.Statement] = set()
        self.root_names: dict[ir.SSAValue, str] = {}
        self.input_types: tuple[types.TypeAttribute, ...] = ()
        self.return_type: types.TypeAttribute = types.Any
        self.parameters: list[Qubit | Register] = []
        self.ordinary_count = 0
        self.output_count = 0

    def meaning(self, value: ir.SSAValue) -> Value:
        """Resolve a temporary expression result to its current source meaning."""
        return self.meanings.get(value, value)

    def value(self, meaning: Value) -> ir.SSAValue:
        """Return a classical value or a temporary name for a quantum location."""
        if isinstance(meaning, ir.SSAValue):
            return meaning
        if isinstance(meaning, (Qubit, Element)):
            typ = QubitType
        elif isinstance(meaning, (Register, View)):
            length = meaning.length.constant if meaning.length is not None else None
            typ = QubitType
            for size in reversed(meaning.row_shape):
                typ = ilist.IListType[
                    typ, types.Int if size is None else types.Literal(size)
                ]
            typ = ilist.IListType[
                typ, types.Int if length is None else types.Literal(length)
            ]
        elif isinstance(meaning, tuple):
            typ = types.Generic(tuple, *(self.value(item).type for item in meaning))
        else:
            typ = types.NoneType
        value = self.bindings.args.append_from(typ)
        self.meanings[value] = meaning
        return value

    def frame(self, state: lowering.State[ast.AST]) -> WireFrame:
        """Get the emission frame and capture the current values of outer allocations."""
        current = state.current_frame
        key = id(current)
        if key not in self.frames:
            self.frames[key] = WireFrame(
                self.emitter.source.code, output=current.curr_block
            )
            self.frame_owners.append(current)
            if current.parent is not None and id(current.parent) in self.frames:
                self.frames[key].entries.update(self.frames[id(current.parent)].entries)
        frame = self.frames[key]
        frame.output = current.curr_block
        for root, name in tuple(self.root_names.items()):
            value = current.get_local(name)
            if value is not None:
                frame.latest[root] = value
        return frame

    def sync(self, state: lowering.State[ast.AST], frame: WireFrame) -> None:
        """Expose updated allocation values to Kirin's region bindings."""
        for root, value in frame.latest.items():
            name = self.root_names.setdefault(root, f"$wire{len(self.root_names)}")
            value.name = name
            state.current_frame.defs[name] = value

    def push(self, state: lowering.State[ast.AST], stmt: ir.Statement) -> ir.Statement:
        """Append a completed wire or classical operation to the current block."""
        self.done.add(stmt)
        return state.current_frame.push(stmt)

    def process(self, state: lowering.State[ast.AST], stmt: ir.Statement) -> None:
        """Resolve one source expression through the shared wire emission tables."""
        frame = self.frame(state)
        frame.current_stmt = stmt
        for value in stmt.args:
            frame.entries[value] = self.meaning(value)
        stmt.detach()
        if isinstance(stmt, func.Invoke) and not is_library(stmt.callee):
            result = (invoke(self, frame, stmt),)
        elif isinstance(stmt, py.assign.TypeAssert) and contains_location(
            frame.get(stmt.got)
        ):
            value = frame.get(stmt.got)
            if not self.value(value).type.is_subseteq(stmt.expected):
                raise lowering.BuildError(
                    f"The quantum value does not match its annotation {stmt.expected}."
                )
            result = (value,)
        elif isinstance(stmt, py.boolop.And | py.boolop.Or):
            raise lowering.BuildError(
                "Boolean operators must lower through conditional expressions."
            )
        else:
            with self.emitter.eval_context():
                self.emitter.state.push_frame(frame)
                try:
                    result = self.emitter.frame_eval(frame, stmt)
                finally:
                    self.emitter.state.pop_frame()
        if not isinstance(result, tuple):
            raise lowering.BuildError(
                f"Expression '{stmt.name}' must produce ordinary results."
            )
        for original, value in zip(stmt.results, result, strict=True):
            self.meanings[original] = value
            if isinstance(value, ir.SSAValue):
                frame.entries[value] = value
            original.type = self.value(value).type
        stmt.drop_all_references()
        self.sync(state, frame)
        self.done.update(frame.output.stmts)

    def visit(self, state: lowering.State[ast.AST], node: ast.AST) -> lowering.Result:
        """Dispatch Python syntax and resolve the operations that its handler creates."""
        result = super().visit(state, node)
        for stmt in tuple(state.current_frame.curr_block.stmts):
            if stmt not in self.done:
                self.process(state, stmt)
        if isinstance(result, ir.Statement):
            values = tuple(self.value(self.meaning(value)) for value in result.results)
            return values
        if isinstance(result, ir.SSAValue):
            return self.value(self.meaning(result))
        return result


def driver(state: lowering.State[ast.AST]) -> Python:
    """Return the wire frontend that owns this Kirin lowering state."""
    return cast(Python, state.parent)
