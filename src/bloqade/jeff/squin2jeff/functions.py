"""Replace wire functions, calls and returns with their Jeff forms."""

from dataclasses import dataclass
from collections.abc import Mapping, Iterator

from kirin import ir, types
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.types import is_subtype
from bloqade.jeff.types import QuregType, is_linear
from bloqade.jeff.dialects import stmts
from bloqade.squin.wire.ownership import owns_inputs
from bloqade.jeff.dialects.stmts.call import declared_outputs

from .kinds import put, fitted, replace, jeff_kind


@dataclass
class Functions(RewriteRule):
    """Retype each function and replace each call and return with Jeff.

    A wire function returns one value, which is a tuple when it has several
    outputs. A Jeff function returns each output as a separate value.
    """

    methods: Mapping[ir.Method, ir.Method]
    """The Jeff copy of each wire method that a call can name.

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
        arguments already hold Jeff values. A borrowing callee returns each register
        argument as the same register, so that result keeps the static length of the
        argument.
        """
        callee = self.methods[node.callee]
        outputs = declared_outputs(callee.return_type)
        made = put(stmts.Call(callee, tuple(node.inputs), outputs), node)
        if not owns_inputs(node.callee):
            borrowed = [value for value in node.inputs if is_linear(value.type)]
            suffix = made.results[len(made.results) - len(borrowed) :]
            for argument, result in zip(borrowed, suffix, strict=True):
                if is_subtype(argument.type, QuregType):
                    result.type = argument.type
        replace(node, nested(node.result.type, iter(made.results), node))


def retype(node: func.Function) -> None:
    """Give the function `node` the Jeff types of its parameters and outputs."""
    inputs = tuple(jeff_kind(kind) for kind in node.signature.inputs)
    outputs = tuple(jeff_kind(kind) for kind in flat_kinds(node.signature.output))
    output = (
        types.NoneType
        if not outputs
        else outputs[0] if len(outputs) == 1 else types.Generic(tuple, *outputs)
    )
    block = node.body.blocks[0]
    for argument, kind in zip(block.args[1:], inputs, strict=True):
        argument.type = kind
    block.args[0].type = types.MethodType[list(inputs), output]
    node.signature = func.Signature(inputs=inputs, output=output)


def returned(node: func.Return) -> None:
    """Replace `node` with a Jeff return of each output in the declared order."""
    function = node.parent_stmt
    if not isinstance(function, func.Function):
        raise ir.ValidationError(node, "Jeff requires returns at function scope.")
    values = flat_values(node.value)
    kinds = declared_outputs(function.signature.output)
    if len(values) != len(kinds):
        raise ir.ValidationError(
            node, "The return values must match the declared function outputs."
        )
    if any(is_subtype(value.type, types.Tuple) for value in values):
        raise ir.ValidationError(
            node, "Jeff returns require flat scalar or array values."
        )
    outputs = (fitted(v, k, node) for v, k in zip(values, kinds, strict=True))
    put(stmts.Return(*outputs), node)
    node.delete()


def flat_kinds(kind: types.TypeAttribute) -> tuple[types.TypeAttribute, ...]:
    """Return the type of each Jeff output of a wire value of type `kind`.

    Jeff has no tuples, so a nested tuple gives its leaf types in order, and None
    gives no output.
    """
    members = declared_outputs(kind)
    if members == (kind,):
        return members
    return tuple(leaf for member in members for leaf in flat_kinds(member))


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
    kind: types.TypeAttribute, results: Iterator[ir.SSAValue], before: ir.Statement
) -> ir.SSAValue:
    """Build a value of the wire type `kind` from the next flat Jeff call results.

    This is the inverse of `flat_kinds`.
    """
    members = declared_outputs(kind)
    if members == (kind,):
        return next(results)
    if not members:
        return put(func.ConstantNone(), before).result
    fields = tuple(nested(member, results, before) for member in members)
    return put(py.tuple.New(fields), before).result
