from dataclasses import field, dataclass

from kirin import ir, rewrite
from kirin.passes import Pass
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.passes.callgraph import CallGraphPass

from bloqade.native import broadcast
from bloqade.squin.clifford import stmts


class GateRule(RewriteRule):
    SQUIN_MAPPING: dict[type[ir.Statement], tuple[ir.Method, ...]] = {
        stmts.X: (broadcast.x,),
        stmts.Y: (broadcast.y,),
        stmts.Z: (broadcast.z,),
        stmts.H: (broadcast.h,),
        stmts.Rx: (broadcast.rx,),
        stmts.Ry: (broadcast.ry,),
        stmts.Rz: (broadcast.rz,),
        stmts.S: (broadcast.s, broadcast.s_adj),
        stmts.T: (broadcast.t, broadcast.t_adj),
        stmts.CX: (broadcast.cx,),
        stmts.CY: (broadcast.cy,),
        stmts.CZ: (broadcast.cz,),
    }

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if (native_methods := self.SQUIN_MAPPING.get(type(node))) is None:
            return RewriteResult()

        if isinstance(node, stmts.SingleQubitNonHermitianGate):
            native_method = native_methods[1] if node.adjoint else native_methods[0]
        else:
            native_method = native_methods[0]

        # do not rewrite in invoke because callgraph pass will be looking for invoke statements
        (callee := py.Constant(native_method)).insert_before(node)
        node.replace_by(func.Call(callee.result, tuple(node.args), kwargs=()))

        return RewriteResult(has_done_something=True)


@dataclass
class SquinToNative(Pass):

    call_graph_pass: CallGraphPass = field(init=False)

    def __post_init__(self):
        rule = rewrite.Walk(GateRule())
        self.call_graph_pass = CallGraphPass(
            self.dialects, rule, no_raise=self.no_raise
        )

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        return self.call_graph_pass.unsafe_run(mt)
