"""This package holds the conversion from squin kernels to jeff dialect IR."""

from bloqade.jeff.analysis.validation import (
    SquinToJeffValidation as SquinToJeffValidation,
)

from .isolate import IsolateRegions as IsolateRegions
from .pipeline import WireToJeff as WireToJeff, SquinToJeff as SquinToJeff
