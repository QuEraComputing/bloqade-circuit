from kirin import ir, types
from kirin.decl import info, statement

from .._dialect import dialect
from ...stim_statement import StimStatement


@statement
class Reset(StimStatement):
    name = "reset"
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
