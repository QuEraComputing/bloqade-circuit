from kirin import ir, types
from kirin.decl import info, statement

from bloqade.stim.dialects.auxiliary import RecordType
from bloqade.stim.dialects.stim_statement import StimStatement


@statement
class Gate(StimStatement):
    name = "stim_gate"
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)
    dagger: bool = info.attribute(default=False)


@statement
class SingleQubitGate(Gate):
    name = "single_qubit_gate"


@statement
class TwoQubitGate(Gate):
    name = "two_qubit_gate"


# control can either be a qubit or a measurement record
@statement
class ControlledTwoQubitGate(Gate):
    name = "controlled_two_qubit_gate"
    controls: tuple[ir.SSAValue, ...] = info.argument(
        types.Union(types.Int, RecordType)
    )
