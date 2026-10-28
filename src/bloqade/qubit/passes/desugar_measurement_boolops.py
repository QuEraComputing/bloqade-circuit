from dataclasses import dataclass

from kirin.ir import Method
from kirin.passes import Pass
from kirin.rewrite import Walk, Chain
from kirin.rewrite.abc import RewriteResult

from ..rewrite import (
    RewriteMeasurementCmp,
    RewriteMeasurementIfElse,
    RewriteMeasurementBooleanOps,
)


@dataclass
class DesugarMeasurementBooleans(Pass):
    """Fully rewrite simple booleans on measurement results to use `is_one`,
    `is_zero` and `is_lost` instead.
    """

    def unsafe_run(self, mt: Method) -> RewriteResult:
        """Run this pass"""
        ruleset = Walk(
            Chain(
                RewriteMeasurementBooleanOps(),
                RewriteMeasurementCmp(),
                RewriteMeasurementIfElse(),
            )
        )
        result = ruleset.rewrite(mt.code)
        return result
