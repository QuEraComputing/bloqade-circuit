from kirin import ir, types, lowering
from kirin.decl import info, statement

from bloqade.qasm2.types import QubitType

dialect = ir.Dialect("qasm2.noise")


@statement(dialect=dialect)
class Pauli1(ir.Statement):
    name = "pauli_1"
    traits = frozenset({lowering.FromPythonCall()})
    px: ir.SSAValue = info.argument(types.Float)
    py: ir.SSAValue = info.argument(types.Float)
    pz: ir.SSAValue = info.argument(types.Float)
    qarg: ir.SSAValue = info.argument(QubitType)
