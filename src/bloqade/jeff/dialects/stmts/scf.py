"""Define the structured control flow statements of jeff.

Each statement mirrors one operation of jeff's scf dialect.

Every region is isolated. Every value that a region uses enters through the block
arguments of the region. Every region ends in a `Yield`. Code that builds a program
must create its regions in this form. The `verify` method of each statement checks
the form.

A family is one of the jeff value families in `bloqade.jeff.types.FAMILIES`.
"""

from collections.abc import Iterable, Sequence

from kirin import ir, types
from kirin.decl import info, statement

from bloqade.jeff.types import is_subtype, same_family

dialect = ir.Dialect("jeff.scf")


@statement(dialect=dialect)
class Yield(ir.Statement):
    """A region terminator that hands the result values to the enclosing statement."""

    traits = frozenset({ir.IsTerminator()})

    values: tuple[ir.SSAValue, ...] = info.argument()

    def __init__(self, *values: ir.SSAValue) -> None:
        """Build a terminator that hands `values` out of a region."""
        super().__init__(
            args=values,
            args_slice={"values": slice(0, None)},
        )


def _one_block(node: ir.Statement) -> None:
    """Raise a validation error unless each region of `node` holds one block."""
    for region in node.regions:
        if len(region.blocks) != 1:
            raise ir.ValidationError(
                node, f"a region of '{node.name}' must hold one block"
            )


def _yields(node: ir.Statement, block: ir.Block, count: int, what: str) -> None:
    """Raise a validation error unless `block` ends in a `Yield` of `count` values.

    The string `what` names the region in the error message.
    """
    terminator = block.last_stmt
    if not isinstance(terminator, Yield):
        raise ir.ValidationError(node, f"{what} must end in a jeff yield")
    if len(terminator.values) != count:
        raise ir.ValidationError(
            node,
            f"{what} yields {len(terminator.values)} values, expected {count}",
        )


def _arguments(
    node: ir.Statement,
    args: Iterable[ir.SSAValue],
    expected: Iterable[ir.SSAValue],
    what: str,
) -> None:
    """Raise a type error if a block argument and its input differ in family."""
    for arg, value in zip(args, expected, strict=True):
        if not same_family(arg.type, value.type):
            raise ir.TypeCheckError(
                node, f"{what} takes {arg.type} where {value.type} comes in"
            )


def _yielded(
    node: ir.Statement,
    block: ir.Block,
    expected: Iterable[ir.SSAValue],
    what: str,
    skip: int = 0,
) -> None:
    """Raise a type error if a yielded value and its carried value differ in family.

    The check ignores the first `skip` yielded values.
    """
    terminator = block.last_stmt
    assert isinstance(terminator, Yield)
    for value, carried in zip(terminator.values[skip:], expected, strict=True):
        if not same_family(value.type, carried.type):
            raise ir.TypeCheckError(
                node, f"{what} yields {value.type} where {carried.type} is carried"
            )


@statement(dialect=dialect, init=False)
class For(ir.Statement):
    """A counted loop statement that runs from `start` to `stop` by `step`.

    The body block takes `(iteration_index, *state)` and yields `(*state)`.
    The results of the loop are the final state.
    """

    traits = frozenset({ir.SSACFG(), ir.IsolatedFromAbove()})
    name = "for"
    start: ir.SSAValue = info.argument(types.Int)
    stop: ir.SSAValue = info.argument(types.Int)
    step: ir.SSAValue = info.argument(types.Int)
    state: tuple[ir.SSAValue, ...] = info.argument()
    body: ir.Region = info.region()

    def __init__(
        self,
        start: ir.SSAValue,
        stop: ir.SSAValue,
        step: ir.SSAValue,
        state: tuple[ir.SSAValue, ...],
        body: ir.Region,
    ) -> None:
        """Build a loop over `range(start, stop, step)` that carries `state`."""
        super().__init__(
            args=(start, stop, step, *state),
            regions=(body,),
            result_types=tuple(value.type for value in state),
            args_slice={
                "start": 0,
                "stop": 1,
                "step": 2,
                "state": slice(3, None),
            },
        )

    def verify(self) -> None:
        """Check that the body takes the index and the state and yields the state."""
        _one_block(self)
        super().verify()
        body = self.body.blocks[0]
        if len(body.args) != 1 + len(self.state):
            raise ir.ValidationError(self, "for-loop body arity mismatch")
        _yields(self, body, len(self.state), "for-loop body")

    def verify_type(self) -> None:
        """Check that the index is an integer and the body keeps the state families."""
        super().verify_type()
        body = self.body.blocks[0]
        if not is_subtype(body.args[0].type, types.Int):
            raise ir.TypeCheckError(
                self, f"for-loop index is {body.args[0].type}, not int"
            )
        _arguments(self, body.args[1:], self.state, "for-loop body")
        _yielded(self, body, self.state, "for-loop body")


@statement(dialect=dialect, init=False)
class Switch(ir.Statement):
    """A branch statement that runs one region chosen by an integer selector.

    Region i handles the selector value i. The last region handles every selector
    that has no case region. Every region holds one block that takes `(*inputs)`
    and yields `(*results)`.
    """

    name = "switch"
    traits = frozenset({ir.SSACFG(), ir.IsolatedFromAbove()})
    selector: ir.SSAValue = info.argument(types.Int)
    inputs: tuple[ir.SSAValue, ...] = info.argument()

    def __init__(
        self,
        selector: ir.SSAValue,
        inputs: tuple[ir.SSAValue, ...],
        branches: Sequence[ir.Region],
        default: ir.Region,
    ) -> None:
        """Build a switch on `selector` that passes `inputs` to the chosen region.

        The `Yield` of the default region sets the result types.

        Raises:
            TypeError: If the default region does not end in a `Yield`.
        """
        terminator = default.blocks[0].last_stmt
        if not isinstance(terminator, Yield):
            raise TypeError("the default region must end in a jeff yield")
        result_types = tuple(value.type for value in terminator.values)
        super().__init__(
            args=(selector, *inputs),
            regions=(*branches, default),
            result_types=result_types,
            args_slice={"selector": 0, "inputs": slice(1, None)},
        )

    def verify(self) -> None:
        """Check that every region takes the inputs and yields the results."""
        _one_block(self)
        super().verify()
        for region in self.regions:
            region.verify()
        for region in self.regions:
            block = region.blocks[0]
            if len(block.args) != len(self.inputs):
                raise ir.ValidationError(self, "switch branch arity mismatch")
            _yields(self, block, len(self.results), "switch branch")

    def verify_type(self) -> None:
        """Check that every region keeps the families of the inputs and the results."""
        super().verify_type()
        for region in self.regions:
            block = region.blocks[0]
            _arguments(self, block.args, self.inputs, "switch branch")
            _yielded(self, block, self.results, "switch branch")
            region.verify_type()

    @property
    def branches(self) -> list[ir.Region]:
        """Return the case regions in selector order."""
        return self.regions[:-1]

    @property
    def default(self) -> ir.Region:
        """Return the region that handles every selector without a case region."""
        return self.regions[-1]


@statement(dialect=dialect, init=False)
class While(ir.Statement):
    """A while loop statement in jeff's two-region form.

    The `before` region receives the loop-carried inputs and yields
    `(condition, *outputs)`. If the condition is true, the `after` region receives
    the outputs and yields the next inputs. If the condition is false, the loop ends.
    The results of the loop are the final outputs.
    """

    traits = frozenset({ir.SSACFG(), ir.IsolatedFromAbove()})
    name = "while"
    inputs: tuple[ir.SSAValue, ...] = info.argument()
    before: ir.Region = info.region()
    after: ir.Region = info.region()

    def __init__(
        self,
        inputs: tuple[ir.SSAValue, ...],
        before: ir.Region,
        after: ir.Region,
    ) -> None:
        """Build a loop whose `before` region checks the condition.

        The `after` region computes the next inputs. The values that the `before`
        region yields after the condition set the result types.

        Raises:
            TypeError: If the `before` region does not end in a `Yield`.
        """
        last = before.blocks[0].last_stmt
        if not isinstance(last, Yield):
            raise TypeError("the before region must end in a jeff yield")
        result_types = tuple(value.type for value in last.values[1:])
        super().__init__(
            args=inputs,
            regions=(before, after),
            result_types=result_types,
            args_slice={"inputs": slice(0, None)},
        )

    def verify(self) -> None:
        """Check the number of arguments and yielded values in both regions.

        The `before` region takes the inputs and yields the condition and the outputs.
        The `after` region takes the outputs and yields the inputs.
        """
        _one_block(self)
        super().verify()
        before, after = self.before.blocks[0], self.after.blocks[0]
        if len(before.args) != len(self.inputs):
            raise ir.ValidationError(self, "while before-region arity mismatch")
        _yields(self, before, 1 + len(self.results), "while before-region")
        if len(after.args) != len(self.results):
            raise ir.ValidationError(self, "while after-region arity mismatch")
        _yields(self, after, len(self.inputs), "while after-region")

    def verify_type(self) -> None:
        """Check that the condition is a bit and the regions keep carried families."""
        super().verify_type()
        before, after = self.before.blocks[0], self.after.blocks[0]
        condition = before.last_stmt
        assert isinstance(condition, Yield)
        if not is_subtype(condition.values[0].type, types.Bool):
            raise ir.TypeCheckError(self, "while before-region must yield a bit first")
        _arguments(self, before.args, self.inputs, "while before-region")
        _yielded(self, before, self.results, "while before-region", skip=1)
        _arguments(self, after.args, self.results, "while after-region")
        _yielded(self, after, self.inputs, "while after-region")
