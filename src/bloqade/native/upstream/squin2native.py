from dataclasses import field, dataclass

from kirin import ir, passes, rewrite
from kirin.dialects import py, func
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.passes.callgraph import CallGraphPass, ReplaceMethods
from kirin.analysis.callgraph import CallGraph

from bloqade.native import kernel, broadcast
from bloqade.squin.clifford import stmts, dialect as clifford_dialect


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
        stmts.Rx: (broadcast.rx,),
        stmts.Ry: (broadcast.ry,),
        stmts.Rz: (broadcast.rz,),
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
class UpdateDialectsOnCallGraph(passes.Pass):
    """Update All dialects on the call graph to a new set of dialects given to this pass.

    Usage:
        pass_ = UpdateDialectsOnCallGraph(rule=rule, dialects=new_dialects)
        pass_(some_method)

    Note: This pass does not update the dialects of the input method, but copies
    all other methods invoked within it before updating their dialects.

    """

    fold_pass: passes.Fold = field(init=False)

    def __post_init__(self):
        self.fold_pass = passes.Fold(self.dialects, no_raise=self.no_raise)

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        mt_map = {}

        cg = CallGraph(mt)

        all_methods = set(sum(map(tuple, cg.defs.values()), ()))
        for original_mt in all_methods:
            if original_mt is mt:
                new_mt = original_mt
            else:
                new_mt = original_mt.similar(self.dialects)
            mt_map[original_mt] = new_mt

        result = RewriteResult()

        for _, new_mt in mt_map.items():
            result = (
                rewrite.Walk(ReplaceMethods(mt_map)).rewrite(new_mt.code).join(result)
            )
            self.fold_pass(new_mt)

        return result


@dataclass
class SquinToNativePass(passes.Pass):

    call_graph_pass: CallGraphPass = field(init=False)

    def __post_init__(self):
        rule = rewrite.Walk(GateRule())
        self.call_graph_pass = CallGraphPass(
            self.dialects, rule, no_raise=self.no_raise
        )

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        return self.call_graph_pass.unsafe_run(mt)


class SquinToNative:
    """A Target that converts Squin Clifford gates to native gates."""

    def emit(self, mt: ir.Method, *, no_raise=True) -> ir.Method:
        """Convert Squin Clifford gates to native gates.

        Args:
            mt (ir.Method): The method to convert.
            no_raise (bool, optional): Whether to suppress errors. Defaults to True.

        Returns:
            ir.Method: The converted method.
        """
        new_dialects = mt.dialects.discard(clifford_dialect).union(kernel)

        out = mt.similar(new_dialects)
        UpdateDialectsOnCallGraph(new_dialects, no_raise=no_raise)(out)
        SquinToNativePass(new_dialects, no_raise=no_raise)(out)
        # verify all kernels in the callgraph
        new_callgraph = CallGraph(out)
        all_kernels = (ker for kers in new_callgraph.defs.values() for ker in kers)
        for ker in all_kernels:
            ker.verify()

        return out
