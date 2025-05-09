from dataclasses import dataclass

from kirin import ir
from kirin.passes import Pass, HintConst, TypeInfer
from kirin.rewrite import (
    Walk,
    Chain,
    Inline,
    Fixpoint,
    Call2Invoke,
    ConstantFold,
    CFGCompactify,
    InlineGetItem,
    InlineGetField,
    DeadCodeElimination,
    CommonSubexpressionElimination,
)
from kirin.dialects import scf, ilist
from kirin.ir.method import Method
from kirin.rewrite.abc import RewriteResult

from bloqade.qasm2.dialects import expr


@dataclass
class QASM2Fold(Pass):
    """Fold pass for qasm2.extended"""

    inline_gate_subroutine: bool = True

    def __post_init__(self):
        self.typeinfer = TypeInfer(self.dialects)

    def unsafe_run(self, mt: Method) -> RewriteResult:
        result = RewriteResult()
        result = (
            HintConst(mt.dialects, no_raise=self.no_raise).unsafe_run(mt).join(result)
        )
        rule = Chain(
            ilist.rewrite.HintLen(),
            ConstantFold(),
            Call2Invoke(),
            InlineGetField(),
            InlineGetItem(),
            DeadCodeElimination(),
            CommonSubexpressionElimination(),
        )
        result = Fixpoint(Walk(rule)).rewrite(mt.code).join(result)

        result = (
            Walk(
                Chain(
                    scf.unroll.PickIfElse(),
                    scf.unroll.ForLoop(),
                    scf.trim.UnusedYield(),
                )
            )
            .rewrite(mt.code)
            .join(result)
        )

        # run typeinfer again after unroll etc. because we now insert
        # a lot of new nodes, which might have more precise types
        self.typeinfer.unsafe_run(mt)
        result = (
            Walk(Chain(ilist.rewrite.ConstList2IList(), ilist.rewrite.Unroll()))
            .rewrite(mt.code)
            .join(result)
        )

        def inline_simple(node: ir.Statement):
            if isinstance(node, expr.GateFunction):
                return self.inline_gate_subroutine

            if not isinstance(node.parent_stmt, (scf.For, scf.IfElse)):
                return True  # always inline calls outside of loops and if-else

            # inside loops and if-else, only inline simple functions, i.e. functions with a single block
            if (trait := node.get_trait(ir.CallableStmtInterface)) is None:
                return False  # not a callable, don't inline to be safe
            region = trait.get_callable_region(node)
            return len(region.blocks) == 1

        result = (
            Walk(
                Inline(inline_simple),
            )
            .rewrite(mt.code)
            .join(result)
        )
        result = Walk(Fixpoint(CFGCompactify())).rewrite(mt.code).join(result)
        return result
