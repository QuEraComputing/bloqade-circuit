from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.ir.method import Method
from kirin.rewrite.abc import RewriteResult

from bloqade.qasm2.dialects import expr
from bloqade.rewrite.passes import AggressiveUnroll

from .unroll_if import UnrollIfs


@dataclass
class QASM2Fold(Pass):
    """Fold pass for qasm2.extended"""

    inline_gate_subroutine: bool = True
    unroll_ifs: bool = True
    aggressive_unroll: AggressiveUnroll = field(init=False)

    def __post_init__(self):
        def inline_simple(node: ir.Statement):
            if isinstance(node, expr.GateFunction):
                return self.inline_gate_subroutine

            return True

        self.aggressive_unroll = AggressiveUnroll(
            self.dialects, inline_simple, no_raise=self.no_raise
        )

    def unsafe_run(self, mt: Method) -> RewriteResult:
        result = RewriteResult()

        if self.unroll_ifs:
            result = UnrollIfs(mt.dialects).unsafe_run(mt).join(result)

        result = self.aggressive_unroll.unsafe_run(mt).join(result)

        return result
