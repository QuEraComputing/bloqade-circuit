from kirin import ir, types, lowering
from kirin.decl import info, statement

from .._dialect import dialect


@statement
class Reset(ir.Statement):
    name = "reset"
    traits = frozenset({lowering.FromPythonCall()})
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class RZ(Reset):
    name = "RZ"


@statement(dialect=dialect)
class RY(Reset):
    name = "RY"


@statement(dialect=dialect)
class RX(Reset):
    name = "RX"
