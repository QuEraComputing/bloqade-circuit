"""Compute index expressions with a Kirin forward analysis."""

from __future__ import annotations

from dataclasses import field, dataclass

from kirin import ir, types
from kirin.analysis import Forward
from kirin.dialects import func
from kirin.analysis.forward import ForwardFrame

from bloqade.constants import constant_int

from .expr import IndexExpr
from .lattice import Index, KnownIndex, UnknownIndex

KEY = "bloqade.indices"
"""Name the registry key of the method tables of `IndexAnalysis`."""


def own_index(value: ir.SSAValue) -> Index:
    """Return the constant index of `value`, or `value` as a symbol of its own.

    A value whose type rules out an integer, such as a list or a qubit, gets no
    index. A value of type `Any` can hold an integer, so it gets a symbol.
    """
    if not (value.type.is_subseteq(types.Int) or types.Int.is_subseteq(value.type)):
        return UnknownIndex()
    constant = constant_int(value)
    return KnownIndex(IndexExpr.of(value) if constant is None else IndexExpr(constant))


@dataclass
class IndexAnalysis(Forward[Index]):
    """Compute the index expression of every value of one function.

    Constants, `+`, `-`, products with a constant and loop variables give index
    expressions. Any other value, such as a parameter or `i * i`, is a symbol of its
    own.
    """

    keys = (KEY,)
    lattice = Index

    def run(self, method: ir.Method, *args: Index, **kwargs: Index):
        """Analyze `method`, with each parameter as a symbol of its own by default."""
        if not args and not kwargs:
            args = tuple(
                own_index(arg) for arg in method.callable_region.blocks[0].args[1:]
            )
        return super().run(method, *args, **kwargs)

    def method_self(self, method: ir.Method) -> Index:
        """Return no index for the function object."""
        return UnknownIndex()

    def eval_fallback(
        self, frame: ForwardFrame[Index], node: ir.Statement
    ) -> tuple[Index, ...]:
        """Give each result its constant index or a symbol of its own."""
        return tuple(own_index(result) for result in node.results)


@dataclass
class Indices:
    """Look up index expressions, and run `IndexAnalysis` once on each function.

    The store analyzes the function of a value on the first lookup of that value.
    """

    dialects: ir.DialectGroup
    facts: dict[ir.SSAValue, IndexExpr] = field(default_factory=dict, init=False)
    analyzed: set[ir.Statement] = field(default_factory=set, init=False)

    def of(self, value: ir.SSAValue) -> IndexExpr:
        """Return the index expression of `value`.

        A value outside every function body is a symbol of its own.
        """
        if value not in self.facts:
            function = defining_function(value)
            if function is not None and function not in self.analyzed:
                self.analyzed.add(function)
                self.facts.update(self.analyze(function))
        return self.facts.get(value, IndexExpr.of(value))

    def analyze(self, function: func.Function) -> dict[ir.SSAValue, IndexExpr]:
        """Run `IndexAnalysis` on `function` and return the index of each value."""
        analysis = IndexAnalysis(self.dialects)
        parameters = function.body.blocks[0].args[1:]
        with analysis.eval_context():
            frame, _ = analysis.call(
                function, UnknownIndex(), *(own_index(arg) for arg in parameters)
            )
        return {
            value: fact.expr
            for value, fact in frame.entries.items()
            if isinstance(fact, KnownIndex)
        }


def defining_function(value: ir.SSAValue) -> func.Function | None:
    """Return the function whose body defines `value`, or None."""
    owner = value.owner
    node = owner if isinstance(owner, ir.Statement) else owner.parent_stmt
    while node is not None and not isinstance(node, func.Function):
        node = node.parent_stmt
    return node
