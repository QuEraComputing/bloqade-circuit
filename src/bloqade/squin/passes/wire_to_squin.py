"""Convert wire methods and their callees back to squin."""

from dataclasses import dataclass

from kirin import ir, types
from kirin.passes import Fold, TypeInfer
from kirin.rewrite import Walk
from kirin.dialects import ilist

from bloqade.types import is_subtype
from bloqade.squin.rewrite.wire.tools import Retype, reachable
from bloqade.squin.rewrite.wire.from_wire import FromWire
from bloqade.squin.analysis.validation.wire import WireValidation


def bounded_list_lengths(typ: types.TypeAttribute) -> types.TypeAttribute:
    """Give each unknown list length of `typ` the bound `int` before the type check.

    The bound assumes no concrete size.
    """
    if isinstance(typ, types.Generic) and is_subtype(typ, ilist.IListType):
        element, length = typ.vars
        return ilist.IListType[
            bounded_list_lengths(element), types.Int if length == types.Any else length
        ]
    if (
        isinstance(typ, types.Generic)
        and is_subtype(typ, types.Tuple)
        and typ.vararg is None
    ):
        return types.Generic(
            tuple, *(bounded_list_lengths(member) for member in typ.vars)
        )
    return typ


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
