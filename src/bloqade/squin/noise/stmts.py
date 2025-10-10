from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import QubitType

from ._dialect import dialect


@statement
class NoiseChannel(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})


@statement
class SingleQubitNoiseChannel(NoiseChannel):
    # NOTE: we are not adding e.g. qubits here, since inheriting then will
    # change the order of the wrapper arguments
    pass


@statement
class TwoQubitNoiseChannel(NoiseChannel):
    pass


@statement(dialect=dialect)
class SingleQubitPauliChannel(SingleQubitNoiseChannel):
    """
    This will apply one of the randomly chosen Pauli operators according to the
    given probabilities (p_x, p_y, p_z).
    """

    px: ir.SSAValue = info.argument(types.Float)
    py: ir.SSAValue = info.argument(types.Float)
    pz: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


N = types.TypeVar("N", bound=types.Int)


@statement(dialect=dialect)
class TwoQubitPauliChannel(TwoQubitNoiseChannel):
    """
    This will apply one of the randomly chosen Pauli products:

    {IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}

    but the choice is weighed with the given probability.

    NOTE: the given parameters are ordered as given in the list above!
    """

    probabilities: ir.SSAValue = info.argument(
        ilist.IListType[QubitType, types.Literal(15)]
    )
    controls: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])
    targets: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])


@statement(dialect=dialect)
class Depolarize(SingleQubitNoiseChannel):
    """
    Apply depolarize error to single qubit.

    This randomly picks one of the three Pauli operators to apply. Each Pauli
    operator has the probability `p / 3` to be selected. No operator is applied
    with the probability `1 - p`.
    """

    p: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


@statement(dialect=dialect)
class Depolarize2(TwoQubitNoiseChannel):
    """
    Apply correlated depolarize error to two qubits

    This will apply one of the randomly chosen Pauli products each with probability `p / 15`:

    `{IX, IY, IZ, XI, XX, XY, XZ, YI, YX, YY, YZ, ZI, ZX, ZY, ZZ}`
    """

    p: ir.SSAValue = info.argument(types.Float)
    controls: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])
    targets: ir.SSAValue = info.argument(ilist.IListType[QubitType, N])


@statement(dialect=dialect)
class QubitLoss(SingleQubitNoiseChannel):
    """
    Apply an atom loss with channel.
    """

    # NOTE: qubit loss error (not supported by Stim)
    p: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(ilist.IListType[QubitType, types.Any])


@statement(dialect=dialect)
class CorrelatedQubitLoss(NoiseChannel):
    """
    Apply a correlated atom loss channel.
    """

    p: ir.SSAValue = info.argument(types.Float)
    qubits: ir.SSAValue = info.argument(
        ilist.IListType[ilist.IListType[QubitType, types.Any], types.Any]
    )
