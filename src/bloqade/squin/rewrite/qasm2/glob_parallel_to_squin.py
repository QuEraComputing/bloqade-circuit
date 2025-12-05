from kirin import ir
from kirin.dialects import func
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.qasm2.dialects import glob, parallel

GLOBAL_PARALLEL_TO_SQUIN_MAP = {
    glob.UGate: squin.broadcast.u3,
    parallel.UGate: squin.broadcast.u3,
    parallel.RZ: squin.broadcast.rz,
}


class QASM2GlobParallelToSquin(RewriteRule):

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:

        if isinstance(node, glob.UGate):
            args = (node.theta, node.phi, node.lam, node.registers)
        elif isinstance(node, parallel.UGate):
            args = (node.theta, node.phi, node.lam, node.qargs)
        elif isinstance(node, parallel.RZ):
            args = (node.theta, node.qargs)
        else:
            return RewriteResult()

        squin_equivalent_stmt = GLOBAL_PARALLEL_TO_SQUIN_MAP[type(node)]
        invoke_stmt = func.Invoke(
            callee=squin_equivalent_stmt,
            inputs=args,
        )
        node.replace_by(invoke_stmt)
        return RewriteResult(has_done_something=True)
