"""Reconstruct squin from Jeff through the wire dialect."""

from dataclasses import dataclass

from kirin import ir

from bloqade.jeff.jeff2wire import JeffToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin


@dataclass
class JeffToSquin:
    """Convert Jeff to wire values and reconstruct reference squin."""

    def emit(self, method: ir.Method) -> ir.Method:
        """Return a squin kernel while preserving the Jeff source and its callees."""
        return WireToSquin().emit(JeffToWire().emit(method))
