"""This package holds the conversion from squin kernels to jeff dialect IR."""

from bloqade.jeff.analysis.validation import (
    SquinToJeffValidation as SquinToJeffValidation,
)

# Importing these modules registers their method tables with the dialects.
from . import (
    py2jeff as py2jeff,
    quantum as quantum,
    scf2jeff as scf2jeff,
    functions as functions,
)
from .pipeline import SquinToJeff as SquinToJeff
from .linearize import Linearize as Linearize
