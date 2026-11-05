"""Give `IndexAnalysis` its rules for integer arithmetic and structured regions."""

from kirin import ir, interp
from kirin.dialects import py, scf, func
from kirin.analysis.forward import ForwardFrame

from .expr import Iter, IndexExpr, loop_values
from .lattice import Index, KnownIndex, UnknownIndex
from .analysis import KEY, IndexAnalysis, own_index


def expr_of(frame: ForwardFrame[Index], value: ir.SSAValue) -> IndexExpr | None:
    """Return the index expression that `frame` holds for `value`, or None."""
    fact = frame.get(value)
    return fact.expr if isinstance(fact, KnownIndex) else None


@py.assign.dialect.register(key=KEY)
class Aliases(interp.MethodTable):
    """Give an alias the index of its operand."""

    @interp.impl(py.assign.Alias)
    def alias(
        self, analysis: IndexAnalysis, frame: ForwardFrame[Index], stmt: py.assign.Alias
    ) -> tuple[Index, ...]:
        """Return the index of the aliased value."""
        return (frame.get(stmt.value),)


@py.binop.dialect.register(key=KEY)
class Arithmetic(interp.MethodTable):
    """Combine the indices of sums, differences and products with a constant."""

    @interp.impl(py.Add)
    def add(
        self, analysis: IndexAnalysis, frame: ForwardFrame[Index], stmt: py.Add
    ) -> tuple[Index, ...]:
        """Return the sum of the operand indices."""
        left, right = expr_of(frame, stmt.lhs), expr_of(frame, stmt.rhs)
        if left is None or right is None:
            return (own_index(stmt.result),)
        return (KnownIndex(left + right),)

    @interp.impl(py.Sub)
    def sub(
        self, analysis: IndexAnalysis, frame: ForwardFrame[Index], stmt: py.Sub
    ) -> tuple[Index, ...]:
        """Return the difference of the operand indices."""
        left, right = expr_of(frame, stmt.lhs), expr_of(frame, stmt.rhs)
        if left is None or right is None:
            return (own_index(stmt.result),)
        return (KnownIndex(left - right),)

    @interp.impl(py.Mult)
    def mult(
        self, analysis: IndexAnalysis, frame: ForwardFrame[Index], stmt: py.Mult
    ) -> tuple[Index, ...]:
        """Scale an index by a constant, or give any other product its own symbol."""
        left, right = expr_of(frame, stmt.lhs), expr_of(frame, stmt.rhs)
        if left is not None and right is not None:
            if (k := left.constant) is not None:
                return (KnownIndex(right.scale(k)),)
            if (k := right.constant) is not None:
                return (KnownIndex(left.scale(k)),)
        return (own_index(stmt.result),)


@py.unary.dialect.register(key=KEY)
class Negation(interp.MethodTable):
    """Negate the index of a unary minus."""

    @interp.impl(py.unary.USub)
    def negate(
        self, analysis: IndexAnalysis, frame: ForwardFrame[Index], stmt: py.unary.USub
    ) -> tuple[Index, ...]:
        """Return the negated index, or a symbol of its own."""
        operand = expr_of(frame, stmt.value)
        if operand is None:
            return (own_index(stmt.result),)
        return (KnownIndex(operand.scale(-1)),)


@scf.dialect.register(key=KEY)
class Regions(interp.MethodTable):
    """Analyze each loop and branch body once and keep its facts in the function."""

    @interp.impl(scf.For)
    def loop(
        self, analysis: IndexAnalysis, frame: ForwardFrame[Index], stmt: scf.For
    ) -> tuple[Index, ...]:
        """Give the loop variable its `Iter` symbol, and each carried value its own."""
        index = KnownIndex(IndexExpr.of(Iter(stmt, loop_values(stmt.iterable))))
        carried = (own_index(arg) for arg in stmt.body.blocks[0].args[1:])
        analyze_body(analysis, frame, stmt, stmt.body, index, *carried)
        return tuple(own_index(result) for result in stmt.results)

    @interp.impl(scf.IfElse)
    def branch(
        self, analysis: IndexAnalysis, frame: ForwardFrame[Index], stmt: scf.IfElse
    ) -> tuple[Index, ...]:
        """Analyze both bodies, and give each result a symbol of its own."""
        for region in (stmt.then_body, stmt.else_body):
            arguments = (own_index(arg) for arg in region.blocks[0].args)
            analyze_body(analysis, frame, stmt, region, *arguments)
        return tuple(own_index(result) for result in stmt.results)

    @interp.impl(scf.Yield)
    def yield_(
        self, analysis: IndexAnalysis, frame: ForwardFrame[Index], stmt: scf.Yield
    ) -> interp.YieldValue[Index]:
        """End a body without facts for the enclosing statement."""
        return interp.YieldValue(tuple(UnknownIndex() for _ in stmt.values))


@func.dialect.register(key=KEY)
class Functions(interp.MethodTable):
    """End the analysis of a function at its return."""

    @interp.impl(func.Return)
    def return_(
        self, analysis: IndexAnalysis, frame: ForwardFrame[Index], stmt: func.Return
    ) -> interp.ReturnValue[Index]:
        """Return no index for the function result."""
        return interp.ReturnValue(UnknownIndex())


def analyze_body(
    analysis: IndexAnalysis,
    frame: ForwardFrame[Index],
    node: ir.Statement,
    region: ir.Region,
    *arguments: Index,
) -> None:
    """Analyze one body of `node` and copy its facts into `frame`."""
    with analysis.new_frame(node, has_parent_access=True) as body:
        analysis.frame_call_region(body, node, region, *arguments)
    frame.entries.update(body.entries)
