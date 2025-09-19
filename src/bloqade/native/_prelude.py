from typing import Annotated

from kirin import ir
from kirin.passes import Default
from kirin.prelude import structural_no_opt
from typing_extensions import Doc

from bloqade.squin import qubit

from .dialects import gates


@ir.dialect_group(structural_no_opt.union([gates, qubit]))
def kernel(self):
    """Compile a function to a native kernel."""

    def run_pass(
        mt,
        *,
        verify: Annotated[
            bool, Doc("run `verify` before running passes, default is `True`")
        ] = True,
        typeinfer: Annotated[
            bool,
            Doc(
                "run type inference and apply the inferred type to IR, default `False`"
            ),
        ] = False,
        fold: Annotated[bool, Doc("run folding passes")] = True,
        aggressive: Annotated[
            bool, Doc("run aggressive folding passes if `fold=True`")
        ] = False,
        no_raise: Annotated[bool, Doc("do not raise exception during analysis")] = True,
    ) -> None:
        default_pass = Default(
            self,
            verify=verify,
            fold=fold,
            aggressive=aggressive,
            typeinfer=typeinfer,
            no_raise=no_raise,
        )
        default_pass.fixpoint(mt)

    return run_pass
