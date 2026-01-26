from itertools import chain

from kirin import ir, rewrite
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.analysis.callgraph import CallGraph

from bloqade.native import kernel, broadcast
from bloqade.squin.gate import stmts, dialect as gate_dialect
from bloqade.rewrite.passes import CallGraphPass, UpdateDialectsOnCallGraph


class GateRule(RewriteRule):
    SQUIN_MAPPING: dict[type[ir.Statement], tuple[ir.Method, ...]] = {
        stmts.X: (broadcast.x,),
        stmts.Y: (broadcast.y,),
        stmts.Z: (broadcast.z,),
        stmts.H: (broadcast.h,),
        stmts.S: (broadcast.s, broadcast.s_adj),
        stmts.T: (broadcast.t, broadcast.t_adj),
        stmts.SqrtX: (broadcast.sqrt_x, broadcast.sqrt_x_adj),
        stmts.SqrtY: (broadcast.sqrt_y, broadcast.sqrt_y_adj),
        stmts.Rx: (broadcast._rx_turns,),
        stmts.Ry: (broadcast._ry_turns,),
        stmts.Rz: (broadcast._rz_turns,),
        stmts.CX: (broadcast.cx,),
        stmts.CY: (broadcast.cy,),
        stmts.CZ: (broadcast.cz,),
        stmts.U3: (broadcast._u3_turns,),
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


class SquinToNative:
    """A Target that converts Squin gates to native gates."""

    def emit(self, mt: ir.Method, *, no_raise=True) -> ir.Method:
        """Convert Squin gates to native gates.

        Args:
            mt (ir.Method): The method to convert.
            no_raise (bool, optional): Whether to suppress errors. Defaults to True.

        Returns:
            ir.Method: The converted method.
        """
        old_callgraph = CallGraph(mt)
        all_dialects = chain.from_iterable(
            ker.dialects.data for kers in old_callgraph.defs.values() for ker in kers
        )
        combined_dialects = mt.dialects.union(all_dialects).union(kernel)

        out = mt.similar(combined_dialects)
        UpdateDialectsOnCallGraph(combined_dialects, no_raise=no_raise)(out)
        CallGraphPass(combined_dialects, rewrite.Walk(GateRule()), no_raise=no_raise)(
            out
        )
        # verify all kernels in the callgraph and discard gate dialect
        out.dialects.discard(gate_dialect)
        new_callgraph = CallGraph(out)
        for ker in new_callgraph.edges.keys():
            ker.dialects.discard(gate_dialect)
            ker.verify()

        return out
