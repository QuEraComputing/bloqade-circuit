"""Replace wire functions, calls and returns with their Jeff forms."""

from dataclasses import dataclass
from collections.abc import Mapping, Iterator

from kirin import ir, types
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.types import is_subtype, output_types
from bloqade.jeff.dialects import stmts
from bloqade.squin.rewrite.wire.tools import put, replace, set_signature
from bloqade.squin.rewrite.wire.signature import packed_type

from .values import fitted, jeff_type


@dataclass
class Functions(RewriteRule):
    """Retype each function and replace each call and return with Jeff.

    A wire function returns one value, which is a tuple when it has several
    outputs. A Jeff function returns each output as a separate value.
    """

    methods: Mapping[ir.Method, ir.Method]
    """Hold the Jeff copy of each wire method that a call can name.

    The pipeline rewrites each callee before its callers, so a call reads the Jeff
    signature of its callee.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Rewrite `node` if it is a function, a call or a return."""
        if isinstance(node, func.Function):
            retype(node)
        elif isinstance(node, func.Invoke):
            self.call(node)
        elif isinstance(node, func.Return):
            returned(node)
        else:
            return RewriteResult()
        return RewriteResult(has_done_something=True)

    def call(self, node: func.Invoke) -> None:
        """Replace `node` with a Jeff call of the Jeff copy of its callee.

        A tuple result becomes nested `py.tuple.New` statements of the call results
        in the shape of the wire result, and later rewrites read their fields. The
        arguments already hold Jeff values. Each call result takes the Jeff type of
        its wire result, which type inference gives the static length of an in-out
        register argument.
        """
        callee = self.methods[node.callee]
        outputs = output_types(callee.return_type)
        made = put(stmts.Call(callee, tuple(node.inputs), outputs), node)
        for result, typ in zip(made.results, flat_types(node.result.type), strict=True):
            result.type = jeff_type(typ)
        replace(node, nested(node.result.type, iter(made.results), node))


def retype(node: func.Function) -> None:
    """Give the function `node` the Jeff types of its parameters and outputs.

    If the walk has rewritten the return already, the outputs take the types of
    the values of the Jeff return.
    """
    inputs = tuple(jeff_type(typ) for typ in node.signature.inputs)
    end = node.body.blocks[0].last_stmt
    if isinstance(end, stmts.Return):
        outputs = tuple(value.type for value in end.values)
    else:
        outputs = tuple(jeff_type(typ) for typ in flat_types(node.signature.output))
    for argument, typ in zip(node.body.blocks[0].args[1:], inputs, strict=True):
        argument.type = typ
    set_signature(node, inputs, packed_type(outputs))


def returned(node: func.Return) -> None:
    """Replace `node` with a Jeff return of each output in the declared order."""
    function = node.parent_stmt
    if not isinstance(function, func.Function):
        raise ir.ValidationError(node, "Jeff requires returns at function scope.")
    values = flat_values(node.value)
    expected = output_types(function.signature.output)
    if len(values) != len(expected):
        raise ir.ValidationError(
            node, "The return values must match the declared function outputs."
        )
    if any(is_subtype(value.type, types.Tuple) for value in values):
        raise ir.ValidationError(
            node, "Jeff returns require flat scalar or array values."
        )
    # Squin can declare a bit where the value is an integer, such as a measurement
    # result that a loop adds 1 to. The output then takes the joined type.
    outputs = tuple(
        fitted(value, jeff_type(typ.join(value.type)), node)
        for value, typ in zip(values, expected, strict=True)
    )
    put(stmts.Return(*outputs), node)
    node.delete()
    output = packed_type(tuple(value.type for value in outputs))
    set_signature(function, function.signature.inputs, output)


def flat_types(typ: types.TypeAttribute) -> tuple[types.TypeAttribute, ...]:
    """Return the type of each Jeff output of a wire value of type `typ`.

    Jeff has no tuples, so a nested tuple gives its leaf types in order, and None
    gives no output.
    """
    members = output_types(typ)
    if members == (typ,):
        return members
    return tuple(leaf for member in members for leaf in flat_types(member))


def flat_values(value: ir.SSAValue) -> tuple[ir.SSAValue, ...]:
    """Return the leaf values of a value that nested `py.tuple.New` statements build.

    None gives no value, and any other value is its own leaf.
    """
    owner = value.owner
    if isinstance(owner, func.ConstantNone):
        return ()
    if isinstance(owner, py.tuple.New):
        return tuple(leaf for item in owner.args for leaf in flat_values(item))
    return (value,)


def nested(
    typ: types.TypeAttribute, results: Iterator[ir.SSAValue], before: ir.Statement
) -> ir.SSAValue:
    """Build a value of the wire type `typ` from the next flat Jeff call results.

    This is the inverse of `flat_types`.
    """
    members = output_types(typ)
    if members == (typ,):
        return next(results)
    if not members:
        return put(func.ConstantNone(), before).result
    fields = tuple(nested(member, results, before) for member in members)
    return put(py.tuple.New(fields), before).result
