"""Convert wire methods and their callees back to squin."""

from dataclasses import dataclass

from kirin import ir
from kirin.passes import Fold, TypeInfer
from kirin.rewrite import Walk

from bloqade.squin.rewrite.wire.tools import Retype, reachable
from bloqade.squin.rewrite.wire.from_wire import FromWire
from bloqade.squin.rewrite.wire.signature import bounded_list_lengths
from bloqade.squin.analysis.validation.wire import WireValidation


@dataclass
class WireToSquin:
    """Convert a wire squin method and every wire callee back to squin kernels."""

    wire_dialects: tuple[ir.Dialect, ...] = ()
    """Hold the dialects of the wire statements that other dialects add, such as Gemini.

    Each of their statements needs a `ReferenceForm` trait.
    """

    def emit(self, method: ir.Method) -> ir.Method:
        """Return a squin kernel that runs the same program as `method`."""
        for callee in reachable(method):
            WireValidation().check(callee)
        kernels = FromWire(wire_dialects=self.wire_dialects).convert(method)
        for copy in kernels.values():
            TypeInfer(copy.dialects)(copy)
            Fold(copy.dialects).unsafe_run(copy)
            Walk(Retype(bounded_list_lengths)).rewrite(copy.code)
            copy.verify()
            copy.verify_type()
        return kernels[method]
