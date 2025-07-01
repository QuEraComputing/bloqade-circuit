"""A NVIDIA QUAKE-like wire dialect.

This dialect is expected to be used in combination with the operator dialect
as an intermediate representation for analysis and optimization of quantum
circuits. Thus we do not define wrapping functions for the statements in this
dialect.
"""

from kirin import ir, types, lowering, exception
from kirin.decl import info, statement
from kirin.dialects import func
from kirin.lowering import wraps
from kirin.ir.attrs.types import TypeAttribute

from bloqade.types import Qubit, QubitType

from .types import MeasurementResultType
from .op.types import Op, OpType

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


@statement(dialect=dialect)
class Wired(ir.Statement):
    traits = frozenset()

    qubits: tuple[ir.SSAValue, ...] = info.argument(QubitType)
    memory_zone: str = info.attribute()
    body: ir.Region = info.region(multi=True)

    def __init__(
        self,
        body: ir.Region,
        *qubits: ir.SSAValue,
        memory_zone: str,
        result_types: tuple[TypeAttribute, ...] | None = None,
    ):
        if result_types is None:
            for block in body.blocks:
                if isinstance(block.last_stmt, Yield):
                    result_types = tuple(arg.type for arg in block.last_stmt.values)
                    break

        if result_types is None:
            result_types = ()

        super().__init__(
            args=qubits,
            args_slice={
                "qubits": slice(0, None),
            },
            regions=[body],
            attributes={
                "memory_zone": ir.PyAttr(memory_zone)
            },  # body of the wired statement
            result_types=result_types,
        )

    def check(self):
        entry_block = self.body.blocks[0]

        if len(entry_block.args) != len(self.qubits):
            raise exception.StaticCheckError(
                f"Expected {len(self.qubits)} arguments, got {len(entry_block.args)}."
            )
        for arg in entry_block.args:
            if not arg.type.is_subseteq(WireType):
                raise exception.StaticCheckError(
                    f"Expected argument of type {WireType}, got {arg.type}."
                )
        for block in self.body.blocks:
            last_stmt = block.last_stmt
            if isinstance(last_stmt, func.Return):
                raise exception.StaticCheckError(
                    "Return statements are not allowed in the body of a Wired statement."
                )
            elif isinstance(last_stmt, Yield) and len(last_stmt.values) != len(
                self.results
            ):
                raise exception.StaticCheckError(
                    f"Expected {len(self.results)} return values, got {len(last_stmt.values)}."
                )


@statement(dialect=dialect)
class Yield(ir.Statement):
    traits = frozenset({})
    values: tuple[ir.SSAValue, ...] = info.argument(WireType)

    def __init__(self, *args: ir.SSAValue):
        super().__init__(
            args=args,
            args_slice={
                "values": slice(0, None),
            },
        )


# In Quake, you put a wire in and get a wire out when you "apply" an operator
# In this case though we just need to indicate that an operator is applied to list[wires]
@statement(dialect=dialect)
class Apply(ir.Statement):  # apply(op, w1, w2, ...)
    traits = frozenset({lowering.FromPythonCall()})
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


# Carry over from Qubit dialect
@statement(dialect=dialect)
class Broadcast(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), ir.Pure()})
    operator: ir.SSAValue = info.argument(OpType)
    inputs: tuple[ir.SSAValue, ...] = info.argument(WireType)

    def __init__(self, operator: ir.SSAValue, *args: ir.SSAValue):
        result_types = tuple(WireType for _ in args)
        super().__init__(
            args=(operator,) + args,
            result_types=result_types,
            args_slice={
                "operator": 0,
                "inputs": slice(1, None),
            },  # pretty printing + syntax sugar
        )  # custom lowering required for wrapper to work here


@statement(dialect=dialect)
class RegionMeasure(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), WireTerminator()})
    wire: ir.SSAValue = info.argument(WireType)
    result: ir.ResultValue = info.result(MeasurementResultType)


# NOTE: measurement cannot be pure because they will collapse the state
#       of the qubit. The state is a hidden state that is not visible to
#      the user in the wire dialect.
@statement(dialect=dialect)
class Measure(ir.Statement):
    traits = frozenset({lowering.FromPythonCall(), WireTerminator()})
    wire: ir.SSAValue = info.argument(WireType)
    qubit: ir.SSAValue = info.argument(QubitType)
    result: ir.ResultValue = info.result(MeasurementResultType)


@statement(dialect=dialect)
class LossResolvingMeasure(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})
    input_wire: ir.SSAValue = info.argument(WireType)
    result: ir.ResultValue = info.result(MeasurementResultType)
    out_wire: ir.ResultValue = info.result(WireType)


@wraps(Unwrap)
def unwrap(qubit: Qubit) -> Wire: ...


@wraps(Apply)
def apply(op: Op, w: Wire) -> Wire: ...
