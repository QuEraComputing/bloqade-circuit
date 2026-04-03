"""Early-termination scf.For constprop for the Stim pipeline.

Kirin's default scf.For constprop iterates the loop body N times for
range(N). For loops where the body produces the same result each
iteration (e.g. REPEAT-eligible loops in Stim), this is redundant --
the analysis converges after 1-2 iterations.

This module registers an early-termination handler under the
"stim.constprop" key on the scf dialect. StimConstProp resolves
"stim.constprop" first, falling back to "constprop" for everything else.
"""

from dataclasses import field, dataclass
from collections.abc import Iterable

from kirin import ir, types, interp
from kirin.rewrite import Walk, WrapConst
from kirin.analysis import const
from kirin.dialects import scf
from kirin.passes.abc import Pass
from kirin.rewrite.abc import RewriteResult
from kirin.analysis.forward import ForwardExtra
from kirin.dialects.scf.stmts import For


@scf.dialect.register(key="stim.constprop")
class _StimScfConstProp(interp.MethodTable):

    @interp.impl(For)
    def for_loop(self, interp_: "StimConstProp", frame: const.Frame, stmt: For):
        iterable = frame.get(stmt.iterable)
        if isinstance(iterable, const.Value):
            return self._prop_const_iterable(interp_, frame, stmt, iterable)
        else:
            return tuple(interp_.lattice.top() for _ in stmt.results)

    def _prop_const_iterable(
        self,
        interp_: "StimConstProp",
        frame: const.Frame,
        stmt: For,
        iterable: const.Value,
    ):
        frame_is_not_pure = False
        if not isinstance(iterable.data, Iterable):
            raise interp.InterpreterError(
                f"Expected iterable, got {type(iterable.data)}"
            )

        loop_vars = frame.get_values(stmt.initializers)

        prev_loop_vars = None
        for value in iterable.data:
            with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
                loop_vars = interp_.frame_call_region(
                    body_frame, stmt, stmt.body, const.Value(value), *loop_vars
                )

            if body_frame.frame_is_not_pure:
                frame_is_not_pure = True
            if loop_vars is None:
                loop_vars = ()

            # Early termination: if loop variables converge between iterations,
            # stop iterating instead of running all N iterations of range(N).
            if prev_loop_vars is not None and loop_vars == prev_loop_vars:
                break
            prev_loop_vars = loop_vars

        if not frame_is_not_pure:
            frame.should_be_pure.add(stmt)
        return loop_vars


@dataclass
class StimConstProp(ForwardExtra[const.Frame, const.Result]):
    """Constant propagation with early-termination for scf.For loops.

    Like kirin's Propagate, but uses the "stim.constprop" key to pick up
    the early-termination handler for scf.For, falling back to "constprop"
    for everything else.

    NOTE: This duplicates Propagate's logic because Propagate is @final.
    Once the early termination is upstreamed into kirin, this class and
    the "stim.constprop" registration can be removed entirely.
    """

    keys = ("stim.constprop", "constprop")
    lattice = const.Result

    _interp: interp.Interpreter = field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        self._interp = interp.Interpreter(
            self.dialects,
            debug=self.debug,
            max_depth=self.max_depth,
            max_python_recursion_depth=self.max_python_recursion_depth,
        )

    def initialize(self):
        super().initialize()
        self._interp.initialize()
        return self

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> const.Frame:
        return const.Frame(node, has_parent_access=has_parent_access)

    def method_self(self, method: ir.Method) -> const.Result:
        return const.Value(method)

    def frame_eval(
        self, frame: const.Frame, node: ir.Statement
    ) -> interp.StatementResult[const.Result]:
        method = self.lookup_registry(frame, node)
        if method is None:
            if node.has_trait(ir.ConstantLike):
                return self.try_eval_const_pure(frame, node, ())
            elif node.has_trait(ir.Pure):
                values = frame.get_values(node.args)
                if types.is_tuple_of(values, const.Value):
                    return self.try_eval_const_pure(frame, node, values)

            if not node.has_trait(ir.Pure):
                frame.frame_is_not_pure = True
            return tuple(const.Unknown() for _ in node._results)

        ret = method(self, frame, node)
        if node.has_trait(ir.IsTerminator) or node.has_trait(ir.Pure):
            return ret
        elif not node.has_trait(ir.MaybePure):
            frame.frame_is_not_pure = True
        elif node not in frame.should_be_pure:
            frame.frame_is_not_pure = True
        return ret

    def try_eval_const_pure(
        self,
        frame: const.Frame,
        stmt: ir.Statement,
        values: tuple[const.Value, ...],
    ) -> interp.StatementResult[const.Result]:
        _frame = self._interp.initialize_frame(frame.code)
        _frame.set_values(stmt.args, tuple(x.data for x in values))
        method = self._interp.lookup_registry(frame, stmt)
        if method is not None:
            value = method(self._interp, _frame, stmt)
        else:
            return tuple(const.Unknown() for _ in stmt.results)
        match value:
            case tuple():
                return tuple(const.Value(each) for each in value)
            case interp.ReturnValue(ret):
                return interp.ReturnValue(const.Value(ret))
            case interp.YieldValue(yields):
                return interp.YieldValue(tuple(const.Value(each) for each in yields))
            case interp.Successor(block, args):
                return interp.Successor(
                    block,
                    *tuple(const.Value(each) for each in args),
                )


@dataclass
class StimHintConst(Pass):
    """HintConst with early-termination scf.For constprop."""

    def unsafe_run(self, mt: ir.Method) -> RewriteResult:
        constprop = StimConstProp(self.dialects)
        if self.no_raise:
            frame, _ = constprop.run_no_raise(mt)
        else:
            frame, _ = constprop.run(mt)
        return Walk(WrapConst(frame)).rewrite(mt.code)
