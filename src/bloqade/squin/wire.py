"""A NVIDIA QUAKE-like wire dialect.

This dialect is expected to be used in combination with the operator dialect
as an intermediate representation for analysis and optimization of quantum
circuits. Thus we do not define wrapping functions for the statements in this
dialect.
"""

from kirin import ir, types, interp, lowering
from kirin.decl import info, statement

from bloqade.types import QubitType

from .op.types import OpType

# from kirin.lowering import wraps

# from .op.types import Op, OpType

dialect = ir.Dialect("squin.wire")


class WireTerminator(ir.StmtTrait):
    pass


class Wire:
    pass


WireType = types.PyClass(Wire)


# no return value for `wrap`
@statement(dialect=dialect)
class Wrap(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), WireTerminator()})
    wire: ir.SSAValue = info.argument(WireType)
    qubit: ir.SSAValue = info.argument(QubitType)


# "Unwrap the quantum references to expose wires" -> From Quake Dialect documentation
# Unwrap(Qubit) -> Wire
@statement(dialect=dialect)
class Unwrap(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), ir.Pure()})
    qubit: ir.SSAValue = info.argument(QubitType)
    result: ir.ResultValue = info.result(WireType)


# In Quake, you put a wire in and get a wire out when you "apply" an operator
# In this case though we just need to indicate that an operator is applied to list[wires]
@statement(dialect=dialect)
class Apply(ir.Statement):  # apply(op, w1, w2, ...)
    traits = frozenset({lowering.FromPythonCall(), ir.Pure()})
    operator: ir.SSAValue = info.argument(OpType)
    inputs: tuple[ir.SSAValue, ...] = info.argument(WireType)

    def __init__(self, operator: ir.SSAValue, *args: ir.SSAValue):
        result_types = tuple(WireType for _ in args)
        super().__init__(
            args=(operator,) + args,
            result_types=result_types,  # result types of the Apply statement, should all be WireTypes
            args_slice={
                "operator": 0,
                "inputs": slice(1, None),
            },  # pretty printing + syntax sugar
        )  # custom lowering required for wrapper to work here


# NOTE: measurement cannot be pure because they will collapse the state
#       of the qubit. The state is a hidden state that is not visible to
#      the user in the wire dialect.
@statement(dialect=dialect)
class Measure(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), WireTerminator()})
    wire: ir.SSAValue = info.argument(WireType)
    result: ir.ResultValue = info.result(types.Int)


@statement(dialect=dialect)
class MeasureAndReset(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), WireTerminator()})
    wire: ir.SSAValue = info.argument(WireType)
    result: ir.ResultValue = info.result(types.Int)
    out_wire: ir.ResultValue = info.result(WireType)


@statement(dialect=dialect)
class Reset(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), WireTerminator()})
    wire: ir.SSAValue = info.argument(WireType)


# Issue where constant propagation can't handle
# multiple return values from Apply properly
@dialect.register(key="constprop")
class ConstPropWire(interp.MethodTable):

    @interp.impl(Apply)
    def apply(self, interp, frame, stmt: Apply):

        return frame.get_values(stmt.inputs)
