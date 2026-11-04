"""Register direct squin-to-wire emission through Kirin method tables.

A dialect outside squin adds its statements with a method table under the key
`emit.squin_wire`. Its methods take an `EmitWire` and a `WireFrame`, and use
`EmitWire.qubits_of`, `EmitWire.operate` and `EmitWire.new_qubit`.
"""

from . import (
    gates as gates,
    control as control,
    functions as functions,
    references as references,
)
from .base import EmitWire as EmitWire, WireFrame as WireFrame
from .values import Qubit as Qubit, Element as Element, Location as Location
