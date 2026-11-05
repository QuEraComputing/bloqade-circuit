"""Check that the types at calls, tuples and regions keep every quantum field.

A wire or a register can cross a call, a tuple or a region only in a type that
names it. For example, a function that returns `tuple[Wire, int]` must declare
that type. `LinearityCheck` then follows each quantum field of such a type.
"""

from dataclasses import dataclass
from collections.abc import Iterable

from kirin import ir, types, interp
from kirin.lattice import EmptyLattice
from kirin.dialects import py, scf, func
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.types import is_subtype
from bloqade.constants import constant_int
from bloqade.squin.wire import stmts
from bloqade.squin.wire.types import linear_paths, nests_linear, contains_linear
from bloqade.squin.wire.ownership import inout_result_type

from .calls import WireCheck, yield_top

KEY: str = "squin.wire.boundaries"
"""Name the registry key of the method tables of `BoundaryCheck`."""


@dataclass
class BoundaryCheck(WireCheck):
    """Record a validation error for each type that hides a quantum field."""

    keys = (KEY, "absint")

    def require_paths(self, node: ir.Statement, typ: types.TypeAttribute) -> None:
        """Require each quantum field of `typ` to sit at a fixed tuple path."""
        try:
            linear_paths(typ)
        except ValueError as error:
            self.error(node, str(error))

    def require_same_paths(
        self,
        node: ir.Statement,
        actual: types.TypeAttribute,
        declared: types.TypeAttribute,
    ) -> None:
        """Require the declared type of a boundary to keep every quantum field."""
        try:
            if linear_paths(actual) != linear_paths(declared):
                self.error(node, "The boundary type must preserve every quantum field.")
        except ValueError as error:
            self.error(node, str(error))

    def require_flat(self, node: ir.Statement, values: Iterable[ir.SSAValue]) -> None:
        """Require control-flow state to carry each quantum value separately."""
        if any(nests_linear(value.type) for value in values):
            self.error(node, "Control flow requires separate wire and register values.")

    def frame_eval(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> interp.StatementResult[EmptyLattice]:
        """Check the types of the results of `node`, then run its rule."""
        if node.dialect is stmts.dialect and any(
            isinstance(value.type, types.BottomType)
            for value in (*node.args, *node.results)
        ):
            self.error(node, "A wire operation cannot use the impossible type Bottom.")
        for result in node.results:
            self.require_paths(node, result.type)
        return super().frame_eval(frame, node)

    def frame_call(
        self,
        frame: ForwardFrame[EmptyLattice],
        node: ir.Statement,
        *args: EmptyLattice,
        **kwargs: EmptyLattice,
    ) -> EmptyLattice:
        """Require separate quantum parameters and a flat output tuple."""
        trait = node.get_trait(ir.CallableStmtInterface)
        if trait is not None:
            for value in trait.get_callable_region(node).blocks[0].args[1:]:
                self.require_paths(node, value.type)
                if nests_linear(value.type):
                    self.error(
                        node,
                        "Quantum function parameters must be separate wires or registers.",
                    )
        if isinstance(node, func.Function):
            output = node.signature.output
            if (
                isinstance(output, types.Generic)
                and is_subtype(output, types.Tuple)
                and any(nests_linear(typ) for typ in output.vars)
            ):
                self.error(
                    node,
                    "Quantum function outputs require a flat tuple of wires and registers.",
                )
        return super().frame_call(frame, node, *args, **kwargs)


@py.tuple.dialect.register(key=KEY)
class Tuples(interp.MethodTable):
    """Check the types of tuple construction and tuple reads."""

    @interp.impl(py.tuple.New)
    def new(
        self,
        check: BoundaryCheck,
        frame: ForwardFrame[EmptyLattice],
        stmt: py.tuple.New,
    ) -> tuple[EmptyLattice, ...]:
        """Require each tuple field to keep the type of its operand."""
        expected = types.Generic(tuple, *(value.type for value in stmt.args))
        if contains_linear(expected) and stmt.result.type != expected:
            check.error(
                stmt, "Tuple construction must preserve every quantum field type."
            )
        return (EmptyLattice.top(),)


@py.indexing.dialect.register(key=KEY)
class Indexing(interp.MethodTable):
    """Check the reads of quantum tuple fields."""

    @interp.impl(py.GetItem)
    def getitem(
        self, check: BoundaryCheck, frame: ForwardFrame[EmptyLattice], stmt: py.GetItem
    ) -> tuple[EmptyLattice, ...]:
        """Require a constant index in bounds and the type of the field it reads."""
        typ = stmt.obj.type
        if not (
            contains_linear(typ)
            and isinstance(typ, types.Generic)
            and is_subtype(typ, types.Tuple)
        ):
            return (EmptyLattice.top(),)
        index, size = constant_int(stmt.index), len(typ.vars)
        if index is None or not -size <= index < size:
            check.error(
                stmt, "A quantum tuple requires a constant index within its bounds."
            )
        elif contains_linear(field := typ.vars[index]) and stmt.result.type != field:
            check.error(stmt, "Tuple extraction must preserve the quantum field type.")
        return (EmptyLattice.top(),)


@func.dialect.register(key=KEY)
class Functions(interp.MethodTable):
    """Check the declared types of calls and returns."""

    @interp.impl(func.Invoke)
    def invoke(
        self, check: BoundaryCheck, frame: ForwardFrame[EmptyLattice], stmt: func.Invoke
    ) -> tuple[EmptyLattice, ...]:
        """Check the argument and result types, then check the callee."""
        parameters = stmt.callee.callable_region.blocks[0].args[1:]
        for argument, parameter in zip(stmt.inputs, parameters):
            check.require_same_paths(stmt, argument.type, parameter.type)
        expected = stmt.callee.return_type
        refined = expected
        if isinstance(stmt.callee.code, func.Function):
            refined = inout_result_type(
                stmt.callee.code, expected, tuple(value.type for value in stmt.inputs)
            )
        if contains_linear(expected) and stmt.result.type not in (expected, refined):
            check.error(
                stmt, "A call result must preserve its declared quantum field types."
            )
        return check.run_callee(stmt)

    @interp.impl(func.Return)
    def return_(
        self, check: BoundaryCheck, frame: ForwardFrame[EmptyLattice], stmt: func.Return
    ) -> interp.ReturnValue[EmptyLattice]:
        """Require the function output type to keep the returned quantum fields."""
        owner = stmt.parent_stmt
        while owner is not None and not isinstance(owner, func.Function):
            owner = owner.parent_stmt
        if isinstance(owner, func.Function):
            check.require_same_paths(stmt, stmt.value.type, owner.signature.output)
        return interp.ReturnValue(EmptyLattice.top())


@scf.dialect.register(key=KEY)
class ControlFlow(interp.MethodTable):
    """Check the state types of loops and branches."""

    @interp.impl(scf.For)
    @interp.impl(scf.IfElse)
    def structured(
        self,
        check: BoundaryCheck,
        frame: ForwardFrame[EmptyLattice],
        stmt: ir.Statement,
    ) -> tuple[EmptyLattice, ...]:
        """Check the state types, then run each body once."""
        check.require_flat(stmt, stmt.results)
        if isinstance(stmt, scf.For):
            check.require_flat(stmt, stmt.initializers)
            for value, argument in zip(stmt.initializers, stmt.body.blocks[0].args[1:]):
                check.require_same_paths(stmt, value.type, argument.type)

        def enter(block: ir.Block) -> None:
            for argument in block.args:
                check.require_paths(stmt, argument.type)

        return check.run_regions(stmt, enter)

    @interp.impl(scf.Yield)
    def yield_(
        self, check: BoundaryCheck, frame: ForwardFrame[EmptyLattice], stmt: scf.Yield
    ) -> interp.YieldValue[EmptyLattice]:
        """Require each yielded type to keep the quantum fields of its region result."""
        check.require_flat(stmt, stmt.values)
        if stmt.parent_stmt is not None:
            for value, result in zip(stmt.values, stmt.parent_stmt.results):
                check.require_same_paths(stmt, value.type, result.type)
        return yield_top(stmt)


class BoundaryValidation(ValidationPass[ForwardFrame[EmptyLattice]]):
    """Check that the types at calls, tuples and regions keep every quantum field."""

    def name(self) -> str:
        """Return the pass name that validation reports show."""
        return "squin wire boundaries"

    def run(
        self, method: ir.Method
    ) -> tuple[ForwardFrame[EmptyLattice], list[ir.ValidationError]]:
        """Run `BoundaryCheck` and return its frame and errors."""
        analysis = BoundaryCheck(method.dialects)
        frame, _ = analysis.run(method)
        return frame, analysis.get_validation_errors()
