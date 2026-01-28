from kirin import ir, types
from kirin.decl import info, statement

from ._dialect import dialect
from ..stim_statement import StimStatement


@statement(dialect=dialect)
class Depolarize1(StimStatement):
    name = "Depolarize1"
    p: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class Depolarize2(StimStatement):
    name = "Depolarize2"
    p: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class PauliChannel1(StimStatement):
    name = "PauliChannel1"
    px: ir.SSAValue = info.argument(types.Float)
    py: ir.SSAValue = info.argument(types.Float)
    pz: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class PauliChannel2(StimStatement):
    name = "PauliChannel2"
    # TODO custom lowering to make sugar for this
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
class XError(StimStatement):
    name = "X_ERROR"
    p: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class YError(StimStatement):
    name = "Y_ERROR"
    p: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement(dialect=dialect)
class ZError(StimStatement):
    name = "Z_ERROR"
    p: ir.SSAValue = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement
class NonStimError(StimStatement):
    name = "NonStimError"
    probs: tuple[ir.SSAValue, ...] = info.argument(types.Float)
    targets: tuple[ir.SSAValue, ...] = info.argument(types.Int)


@statement
class NonStimCorrelatedError(StimStatement):
    name = "NonStimCorrelatedError"
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


@statement(dialect=dialect)
class CorrelatedQubitLoss(NonStimCorrelatedError):
    name = "correlated_loss"
