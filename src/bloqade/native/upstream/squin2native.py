from dataclasses import dataclass

from kirin import ir
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.native import broadcast
from bloqade.squin.clifford import stmts


@dataclass
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

        inputs = tuple(node.args)
        node.replace_by(func.Invoke(inputs, callee=native_method, kwargs=()))

        return RewriteResult(has_done_something=True)
