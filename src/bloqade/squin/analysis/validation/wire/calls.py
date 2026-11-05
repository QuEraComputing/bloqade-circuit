"""Share the call cache and the traversal of the wire validation analyses."""

from abc import ABC
from typing import Any, TypeVar
from dataclasses import field, dataclass
from collections.abc import Callable

from kirin import ir, interp, lattice
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.dialects import scf, func
from typing_extensions import Self
from kirin.analysis.forward import ForwardFrame

LatticeType = TypeVar("LatticeType", bound=lattice.BoundedLattice)


@dataclass
class CachedCalls(Forward[LatticeType], ABC):
    """Interpret each callee once for each list of abstract arguments.

    Without reuse, a chain of calls costs exponential time in its depth. Each error sits
    at a callee node, so a reused result loses no error.
    """

    calls: dict[tuple[Any, ...], tuple[ForwardFrame[LatticeType], LatticeType]] = field(
        default_factory=dict, init=False
    )
    """Hold the frame and the result of each finished call, keyed by callee and arguments."""

    def initialize(self) -> Self:
        """Forget the results of the previous analysis run."""
        super().initialize()
        self.calls = {}
        return self

    def call(
        self, node: ir.Statement | ir.Method, *args: LatticeType, **kwargs: LatticeType
    ) -> tuple[ForwardFrame[LatticeType], LatticeType]:
        """Return the stored result of an equal call, or interpret the callee."""
        key = (node, args, tuple(kwargs.items()))
        if key not in self.calls:
            self.calls[key] = super().call(node, *args, **kwargs)
        return self.calls[key]


@dataclass
class WireCheck(CachedCalls[EmptyLattice], ABC):
    """Visit each statement of a wire method and its callees once, and record errors.

    A check without abstract values uses this base. Its method tables call
    `run_regions` and `run_callee` to visit loops, branches and callees.
    """

    lattice = EmptyLattice

    def method_self(self, method: ir.Method) -> EmptyLattice:
        """Return the top element for the method object."""
        return EmptyLattice.top()

    def error(self, node: ir.IRNode, message: str) -> None:
        """Record the validation error `message` at `node`."""
        self.add_validation_error(node, ir.ValidationError(node, message))

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> tuple[EmptyLattice, ...]:
        """Return the top element for each result of a statement without a rule."""
        return tuple(EmptyLattice.top() for _ in node.results)

    def run_regions(
        self, stmt: ir.Statement, enter: Callable[[ir.Block], None]
    ) -> tuple[EmptyLattice, ...]:
        """Call `enter` on each body block of `stmt`, and then visit the body once."""
        for region in stmt.regions:
            if not region.blocks:
                continue
            block = region.blocks[0]
            enter(block)
            with self.new_frame(stmt, has_parent_access=True) as inner:
                self.frame_call_region(
                    inner, stmt, region, *(EmptyLattice.top() for _ in block.args)
                )
        return tuple(EmptyLattice.top() for _ in stmt.results)

    def run_callee(self, stmt: func.Invoke) -> tuple[EmptyLattice, ...]:
        """Visit the callee of `stmt` once."""
        parameters = stmt.callee.callable_region.blocks[0].args[1:]
        self.call(
            stmt.callee.code,
            EmptyLattice.top(),
            *(EmptyLattice.top() for _ in parameters),
        )
        return (EmptyLattice.top(),)


def yield_top(stmt: scf.Yield) -> interp.YieldValue[EmptyLattice]:
    """Return the top element for each value of the yield `stmt`."""
    return interp.YieldValue(tuple(EmptyLattice.top() for _ in stmt.values))
