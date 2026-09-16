"""This module holds the traversal and error reporting that jeff analyses share."""

from abc import ABC
from typing import TypeVar, ClassVar
from dataclasses import field, dataclass
from collections.abc import Iterable

from kirin import ir, interp, lattice
from kirin.analysis.forward import Forward, ForwardFrame

from bloqade.jeff.dialects import stmts

SHARED_KEY = "validate.jeff"
"""The registry key of the rules that all analyses share."""

L = TypeVar("L", bound=lattice.BoundedLattice)


@dataclass
class Check(Forward[L], ABC):
    """A forward analysis that records validation errors at IR nodes."""

    isolated: ClassVar[bool] = False
    """If true, each region of an isolated statement runs in a fresh frame."""

    visited: set[tuple[ir.Statement, tuple[L, ...]]] = field(
        default_factory=set, init=False
    )
    """The functions that the analysis has entered, each with its argument values."""

    def initialize(self) -> "Check[L]":
        """Reset the interpreter state and the set of entered functions."""
        super().initialize()
        self.visited = set()
        return self

    def run(
        self, method: ir.Method, *args: L, **kwargs: L
    ) -> tuple[ForwardFrame[L], L]:
        """Analyze `method` and every function that it calls.

        Every parameter of `method` gets lattice top.
        """
        params = [self.lattice.top() for _ in _parameters(method)]
        with self.eval_context():
            return self.call(method.code, self.method_self(method), *params)

    def method_self(self, method: ir.Method) -> L:
        """Return lattice top for the method object."""
        return self.lattice.top()

    def error(self, node: ir.IRNode, message: str) -> None:
        """Record a validation error at an IR node."""
        self.add_validation_error(node, ir.ValidationError(node, message))

    def enter_function(self, code: ir.Statement) -> bool:
        """Return True if the analysis can run the body of the function `code`.

        The analysis can run a body that holds one block and ends in a jeff return.
        """
        blocks = (
            code.get_present_trait(ir.CallableStmtInterface)
            .get_callable_region(code)
            .blocks
        )
        return len(blocks) == 1 and isinstance(blocks[0].last_stmt, stmts.Return)

    def leave_function(self, frame: ForwardFrame[L]) -> None:
        """Inspect the frame of a function after the analysis ran its body.

        The default does nothing.
        """

    def operand_missing(
        self, frame: ForwardFrame[L], node: ir.Statement, value: ir.SSAValue
    ) -> None:
        """Handle an operand that has no entry in the current frame.

        The default does nothing.
        """

    def read(
        self, frame: ForwardFrame[L], node: ir.Statement, values: Iterable[ir.SSAValue]
    ) -> tuple[L, ...]:
        """Return the lattice values of the operands `values` of `node`.

        For an operand that the frame does not hold, the method calls
        `operand_missing` and stores lattice top.
        """
        results: list[L] = []
        for value in values:
            result = frame.entries.get(value)
            if result is None:
                self.operand_missing(frame, node, value)
                result = self.lattice.top()
                frame.set(value, result)
            results.append(result)
        return tuple(results)

    def frame_call(
        self, frame: ForwardFrame[L], node: ir.Statement, *args: L, **kwargs: L
    ) -> L:
        """Check a function before and after the analysis runs its body.

        If the analysis cannot run the body, the method returns lattice bottom.
        """
        self.visited.add((node, args))
        if not self.enter_function(node):
            return self.lattice.bottom()
        result = super().frame_call(frame, node, *args, **kwargs)
        self.leave_function(frame)
        return result

    def frame_eval(
        self, frame: ForwardFrame[L], node: ir.Statement
    ) -> interp.StatementResult[L]:
        """Run the transfer rule of a statement, or the fallback rule if it has none."""
        rule = self.lookup_registry(frame, node)
        if rule is not None:
            return rule(self, frame, node)
        return self.eval_fallback(frame, node)

    def eval_fallback(
        self, frame: ForwardFrame[L], node: ir.Statement
    ) -> interp.StatementResult[L]:
        """Read the operands and give each result lattice top."""
        self.read(frame, node, node.args)
        return tuple(self.lattice.top() for _ in node.results)


@stmts.scf.dialect.register(key=SHARED_KEY)
class _Regions(interp.MethodTable):
    """A method table that runs each region of a jeff control-flow statement once."""

    @interp.impl(stmts.For)
    @interp.impl(stmts.Switch)
    @interp.impl(stmts.While)
    def structured(
        self, check: Check[L], frame: ForwardFrame[L], stmt: ir.Statement
    ) -> tuple[L, ...]:
        """Run every region once with lattice top as its arguments.

        If the analysis is isolated and the statement has the `IsolatedFromAbove` trait,
        each region runs in a fresh frame.
        """
        check.read(frame, stmt, stmt.args)
        top = check.lattice.top()
        for region in stmt.regions:
            if not region.blocks:
                continue
            args = [top for _ in region.blocks[0].args]
            if check.isolated and stmt.has_trait(ir.IsolatedFromAbove):
                # The fresh frame holds no outer values.
                # So each read from outside the region reaches `operand_missing`.
                with check.new_frame(stmt) as inner:
                    check.frame_call_region(inner, stmt, region, *args)
            else:
                check.frame_call_region(frame, stmt, region, *args)
        return tuple(top for _ in stmt.results)

    @interp.impl(stmts.Yield)
    def yield_(
        self, check: Check[L], frame: ForwardFrame[L], stmt: stmts.Yield
    ) -> interp.YieldValue[L]:
        """End the region with the yielded values."""
        return interp.YieldValue(check.read(frame, stmt, stmt.values))


@stmts.call.dialect.register(key=SHARED_KEY)
class _Calls(interp.MethodTable):
    """A method table that enters each callee function once."""

    @interp.impl(stmts.Call)
    def call(
        self, check: Check[L], frame: ForwardFrame[L], stmt: stmts.Call
    ) -> tuple[L, ...]:
        """Read the inputs, then analyze the callee once per set of argument values."""
        check.read(frame, stmt, stmt.inputs)
        top = check.lattice.top()
        callee = stmt.callee
        if isinstance(callee, ir.Method):
            args = (check.method_self(callee), *(top for _ in _parameters(callee)))
            if (callee.code, args) not in check.visited:
                check.call(callee.code, *args)
        return tuple(top for _ in stmt.results)


def _parameters(method: ir.Method) -> list[ir.BlockArgument]:
    """Return the parameters of `method`, or no parameters if its body has no block."""
    blocks = method.callable_region.blocks
    return list(blocks[0].args[1:]) if blocks else []
