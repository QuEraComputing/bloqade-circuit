"""Cirq emit method registration.

Imports dialect emit modules to register method tables and exposes
``emit_circuit``.
"""

# NOTE: just to register methods
from . import (
    scf as scf,
    gate as gate,
    noise as noise,
    qubit as qubit,
    annotate as annotate,
)
from .base import emit_circuit as emit_circuit
