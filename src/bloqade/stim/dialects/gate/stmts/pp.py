from kirin import ir, types, lowering
from kirin.decl import info, statement

from .._dialect import dialect
from ...auxiliary.types import PauliStringType


# Generalized Pauli-product gates
# ---------------------------------------
@statement(dialect=dialect)
class SPP(ir.Statement):
    name = "SPP"
    traits = frozenset({lowering.FromPythonCall()})
    dagger: bool = info.attribute(types.Bool, default=False)
    tag: str = info.attribute(types.String, default=None)
    targets: tuple[ir.SSAValue, ...] = info.argument(PauliStringType)
