"""This module holds `JeffToSquin`, which converts a jeff method to a squin kernel."""

from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Fold
from kirin.rewrite import Walk
from kirin.ir.exception import ValidationErrorGroup
from kirin.dialects.scf.unroll import PickIfElse

from bloqade import squin
from bloqade.jeff.dialects import stmts, kernel as jeff_kernel
from bloqade.jeff.analysis.wire import WireReferenceAnalysis
from bloqade.jeff.analysis.validation import JeffToSquinValidation

from .jeff2py import JeffToPy
from .jeff2scf import JeffToScf
from .delinearize import Conversion, Delinearize


@dataclass
class JeffToSquin:
    """A target that converts jeff dialect IR to squin kernels."""

    conversions: dict[ir.Method, Conversion] = field(default_factory=dict, init=False)
    """The conversion of each jeff function of the last `emit`."""

    def emit(self, method: ir.Method) -> ir.Method:
        """Return the squin kernel for `method` and leave `method` as it is.

        If squin cannot express a construct of `method`, the method raises a
        `ValidationErrorGroup`.
        Squin integers do not wrap, so a result outside the int32 range differs.
        """
        if method.dialects is not jeff_kernel:
            raise ValueError(
                "JeffToSquin expects a method on the dialect group `jeff.kernel`."
            )
        _, errors = JeffToSquinValidation().run(method)
        if errors:
            raise ValidationErrorGroup(
                f"JeffToSquin cannot express '{method.sym_name}'. "
                f"Unsupported constructs: {len(errors)}.",
                errors,
            )
        # Every conversion exists before any body is rewritten, so that a call
        # finds its callee's kernel, also in a recursion. The passes mix kirin
        # statements into the jeff code, hence the union of the groups.
        self.conversions = {}
        for function in _functions(method):
            kernel = function.similar(jeff_kernel.union(squin.kernel))
            JeffToPy(kernel.dialects).unsafe_run(kernel)
            JeffToScf(kernel.dialects).unsafe_run(kernel)
            frame, _ = WireReferenceAnalysis(kernel.dialects).run(kernel)
            self.conversions[function] = Conversion(kernel, frame.entries)
        for kernel in (c.kernel for c in self.conversions.values()):
            Delinearize(kernel.dialects, conversions=self.conversions).unsafe_run(
                kernel
            )
            kernel.dialects = squin.kernel
        # Squin's type inference types a callee when it first reaches a call.
        # So it runs after every function is squin code.
        for kernel in (c.kernel for c in self.conversions.values()):
            # A switch on a constant selector leaves a branch that never runs.
            # Folding removes it, so that no later pass has to reason about it.
            fold = Fold(kernel.dialects)
            fold.unsafe_run(kernel)
            while Walk(PickIfElse()).rewrite(kernel.code).has_done_something:
                fold.unsafe_run(kernel)
            if run_pass := squin.kernel.run_pass:
                run_pass(kernel, fold=False)
        # return the converted kernel for the requested method
        return self.conversions[method].kernel


def _functions(method: ir.Method) -> list[ir.Method]:
    """Return `method` and every jeff function that its calls reach, callees first.

    Squin's type inference types a callee from the caller when it reaches the
    call, without the callee's constant hints. So each kernel gets its passes
    before its callers do.
    """
    seen: set[ir.Method] = set()
    order: list[ir.Method] = []

    def visit(function: ir.Method) -> None:
        if function in seen:
            return
        seen.add(function)
        for node in function.callable_region.walk():
            if isinstance(node, stmts.Call):
                visit(node.callee)
        order.append(function)

    visit(method)
    return order
