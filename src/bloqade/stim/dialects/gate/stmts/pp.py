from kirin import ir, types
from kirin.decl import info, statement

from .._dialect import dialect
from ...stim_statement import StimStatement
from ...auxiliary.types import PauliStringType


# Generalized Pauli-product gates
# ---------------------------------------
@statement(dialect=dialect)
class SPP(StimStatement):
    name = "SPP"
    dagger: bool = info.attribute(types.Bool, default=False)
    targets: tuple[ir.SSAValue, ...] = info.argument(PauliStringType)
