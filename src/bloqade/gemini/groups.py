from typing import Annotated

from kirin import ir
from kirin.passes import Default
from kirin.prelude import structural_no_opt
from kirin.dialects import py, func, ilist
from typing_extensions import Doc
from kirin.passes.inline import InlinePass

from bloqade.squin import gate, qubit
from bloqade.validation import KernelValidation
from bloqade.rewrite.passes import AggressiveUnroll

from .analysis import GeminiLogicalValidationAnalysis


@ir.dialect_group(structural_no_opt.union([gate, py.constant, qubit, func, ilist]))
def logical(self):
    """Compile a function to a Gemini logical kernel."""

    def run_pass(
        mt,
        *,
        verify: Annotated[
            bool, Doc("run `verify` before running passes, default is `True`")
        ] = True,
        typeinfer: Annotated[
            bool,
            Doc("run type inference and apply the inferred type to IR, default `True`"),
        ] = True,
        fold: Annotated[bool, Doc("run folding passes")] = True,
        aggressive: Annotated[
            bool, Doc("run aggressive folding passes if `fold=True`")
        ] = False,
        inline: Annotated[bool, Doc("inline function calls, default `True`")] = True,
        aggressive_unroll: Annotated[
            bool,
            Doc(
                "Run aggressive inlining and unrolling pass on the IR, default `False`"
            ),
        ] = False,
        no_raise: Annotated[bool, Doc("do not raise exception during analysis")] = True,
    ) -> None:

        if aggressive_unroll:
            AggressiveUnroll(mt.dialects, no_raise=no_raise).fixpoint(mt)
        else:
            default_pass = Default(
                self,
                verify=verify,
                fold=fold,
                aggressive=aggressive,
                typeinfer=typeinfer,
                no_raise=no_raise,
            )

            default_pass.fixpoint(mt)

        if inline and not aggressive_unroll:
            InlinePass(mt.dialects, no_raise=no_raise).fixpoint(mt)

        if verify:
            validator = KernelValidation(GeminiLogicalValidationAnalysis)
            validator.run(mt, no_raise=no_raise)
            mt.verify()

    return run_pass
