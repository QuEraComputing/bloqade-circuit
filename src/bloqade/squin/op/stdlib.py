from kirin import ir
from kirin.prelude import structural_no_opt

from . import types
from ._dialect import dialect
from ._wrapper import h, x, y, z, rot, phase, control


@ir.dialect_group(structural_no_opt.add(dialect))
def op(self):
    def run_pass(method):
        pass

    return run_pass


@op
def rx(theta: float) -> types.Op:
    """Rotation X gate."""
    return rot(x(), theta)


@op
def ry(theta: float) -> types.Op:
    """Rotation Y gate."""
    return rot(y(), theta)


@op
def rz(theta: float) -> types.Op:
    """Rotation Z gate."""
    return rot(z(), theta)


@op
def cx() -> types.Op:
    """Controlled X gate."""
    return control(x(), n_controls=1)


@op
def cy() -> types.Op:
    """Controlled Y gate."""
    return control(y(), n_controls=1)


@op
def cz() -> types.Op:
    """Control Z gate."""
    return control(z(), n_controls=1)


@op
def ch() -> types.Op:
    """Control H gate."""
    return control(h(), n_controls=1)


@op
def cphase(theta: float) -> types.Op:
    """Control Phase gate."""
    return control(phase(theta), n_controls=1)
