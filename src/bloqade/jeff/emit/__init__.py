"""This module holds the emitter from jeff dialect IR to jeff modules."""

# Importing these modules registers their method tables with the dialects.
from . import (
    scf as scf,
    call as call,
    func as func,
    gate as gate,
    wire as wire,
    classical as classical,
)
from .base import EmitJeff as EmitJeff
from .target import emit_jeff as emit_jeff
