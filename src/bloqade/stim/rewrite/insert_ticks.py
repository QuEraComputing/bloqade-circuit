from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.stim.dialects import gate, noise, collapse, auxiliary

# Stim dialects whose statements advance a circuit "moment" / time step. A TICK
# after every such operation forces Stim to render one moment per step instead
# of ASAP-packing the diagram. Statements in the auxiliary dialect (constants,
# records, detectors, observables, coordinate annotations) and control flow do
# not advance a moment, so they are left untouched -- measurement-record and
# detector indexing are unaffected.
OPERATION_DIALECTS = frozenset({gate.dialect, collapse.dialect, noise.dialect})


class InsertTicks(RewriteRule):
    """Insert a ``TICK`` after every Stim operation.

    Operates on a lowered Stim circuit. After each operation statement (gate,
    reset, measurement, or noise channel) a
    :class:`~bloqade.stim.dialects.auxiliary.stmts.Tick` is inserted, so the
    rendered diagram's columns follow program order rather than ASAP packing.

    The rule is idempotent -- an operation already followed by a ``TICK`` is
    left untouched -- so it is safe under :class:`~kirin.rewrite.Fixpoint`.
    """

    @staticmethod
    def is_operation(stmt: ir.Statement) -> bool:
        """Whether the statement is a moment-advancing Stim operation."""
        return getattr(stmt, "dialect", None) in OPERATION_DIALECTS

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Insert a ``TICK`` after ``node`` when it is an un-ticked operation."""
        if not self.is_operation(node):
            return RewriteResult()

        if isinstance(node.next_stmt, auxiliary.stmts.Tick):
            return RewriteResult()

        auxiliary.stmts.Tick().insert_after(node)
        return RewriteResult(has_done_something=True)
