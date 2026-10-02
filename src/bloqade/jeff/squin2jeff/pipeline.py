"""This module holds `SquinToJeff`, which converts a squin kernel to a jeff method."""

from dataclasses import dataclass

from kirin import ir
from kirin.rewrite import Walk, Fixpoint, DeadCodeElimination
from kirin.dialects import func
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.jeff.forms import is_library
from bloqade.analysis.reference import Ref
from bloqade.jeff.analysis.validation import SquinToJeffValidation
from bloqade.squin.analysis.reference import QubitReferenceAnalysis

from .isolate import IsolateRegions
from .linearize import Linearize


@dataclass
class SquinToJeff:
    """A target that converts squin kernels to jeff dialect IR."""

    def emit(self, method: ir.Method) -> ir.Method:
        """Return the jeff method for `method` and leave `method` as it is.

        If jeff cannot express a construct of `method`, the method raises a
        `ValidationErrorGroup`.
        """
        if method.dialects is not squin.kernel:
            raise ValueError(
                "SquinToJeff expects a method on the dialect group `squin.kernel`."
            )
        analysis = QubitReferenceAnalysis(method.dialects)
        refs: dict[ir.SSAValue, Ref] = {}
        errors: list[ir.ValidationError] = []
        for kernel in _kernels(method):
            frame, _ = analysis.run(kernel)
            validation = SquinToJeffValidation()
            validation.set_analysis_cache({QubitReferenceAnalysis: frame})
            errors += validation.run(kernel)[1]
            # Each SSA value belongs to one kernel, so no entry overwrites another.
            refs.update(frame.entries)
        if errors:
            raise ValidationErrorGroup(
                f"SquinToJeff cannot express '{method.sym_name}'. "
                f"Unsupported constructs: {len(errors)}.",
                errors,
            )
        emitter = Linearize(method.dialects, refs)
        emitter.run(method.code)
        for function in emitter.functions.values():
            IsolateRegions(function.dialects).unsafe_run(function)
            Fixpoint(Walk(DeadCodeElimination())).rewrite(function.code)
        return emitter.functions[method.code]


def _kernels(method: ir.Method) -> list[ir.Method]:
    """Return `method` and every user kernel that its calls reach.

    A library kernel, such as a gate or `qalloc`, becomes jeff statements, so it
    has no references of its own.
    """
    seen: set[ir.Method] = set()
    order: list[ir.Method] = []

    def visit(kernel: ir.Method) -> None:
        if kernel in seen:
            return
        seen.add(kernel)
        order.append(kernel)
        for node in kernel.callable_region.walk():
            if isinstance(node, func.Invoke) and not is_library(node.callee):
                visit(node.callee)

    visit(method)
    return order
