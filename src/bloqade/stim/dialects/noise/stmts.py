from kirin import ir, types, lowering
from kirin.decl import info, statement

from ._dialect import dialect


@statement(dialect=dialect)
class Depolarize1(ir.Statement):
    name = "Depolarize1"
    traits = frozenset({lowering.FromPythonCall()})
    p: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class Depolarize2(ir.Statement):
    name = "Depolarize2"
    traits = frozenset({lowering.FromPythonCall()})
    p: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class PauliChannel1(ir.Statement):
    name = "PauliChannel1"
    traits = frozenset({lowering.FromPythonCall()})
    px: ir.SSAValue = info.argument(types.Float)
    py: ir.SSAValue = info.argument(types.Float)
    pz: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class PauliChannel2(ir.Statement):
    name = "PauliChannel2"
    # TODO custom lowering to make sugar for this
    traits = frozenset({lowering.FromPythonCall()})
    pix: ir.SSAValue = info.argument(types.Float)
    piy: ir.SSAValue = info.argument(types.Float)
    piz: ir.SSAValue = info.argument(types.Float)
    pxi: ir.SSAValue = info.argument(types.Float)
    pxx: ir.SSAValue = info.argument(types.Float)
    pxy: ir.SSAValue = info.argument(types.Float)
    pxz: ir.SSAValue = info.argument(types.Float)
    pyi: ir.SSAValue = info.argument(types.Float)
    pyx: ir.SSAValue = info.argument(types.Float)
    pyy: ir.SSAValue = info.argument(types.Float)
    pyz: ir.SSAValue = info.argument(types.Float)
    pzi: ir.SSAValue = info.argument(types.Float)
    pzx: ir.SSAValue = info.argument(types.Float)
    pzy: ir.SSAValue = info.argument(types.Float)
    pzz: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class XError(ir.Statement):
    name = "X_ERROR"
    traits = frozenset({lowering.FromPythonCall()})
    p: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class YError(ir.Statement):
    name = "Y_ERROR"
    traits = frozenset({lowering.FromPythonCall()})
    p: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class ZError(ir.Statement):
    name = "Z_ERROR"
    traits = frozenset({lowering.FromPythonCall()})
    p: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement
class NonStimError(ir.Statement):
    name = "NonStimError"
    traits = frozenset({lowering.FromPythonCall()})
    probs: tuple[ir.SSAValue, ...] = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement
class NonStimCorrelatedError(ir.Statement):
    name = "NonStimCorrelatedError"
    traits = frozenset({lowering.FromPythonCall()})
    nonce: int = (
        info.attribute()
    )  # Must be a unique value, otherwise stim might merge two correlated errors with equal probabilities
    probs: tuple[ir.SSAValue, ...] = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class TrivialCorrelatedError(NonStimCorrelatedError):
    name = "TRIV_CORR_ERROR"


@statement(dialect=dialect)
class TrivialError(NonStimError):
    name = "TRIV_ERROR"


@statement(dialect=dialect)
class QubitLoss(NonStimError):
    name = "loss"
