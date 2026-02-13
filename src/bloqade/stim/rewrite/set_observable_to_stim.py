from dataclasses import dataclass

from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.stim.dialects.auxiliary import ObservableInclude
from bloqade.analysis.measure_id.lattice import MeasureIdTuple
from bloqade.decoders.dialects.annotate.stmts import SetObservable

from ..rewrite.get_record_util import insert_get_records


@dataclass
class SetObservableToStim(RewriteRule):
    """
    Rewrite SetObservable to GetRecord and ObservableInclude in the stim dialect
    """

    measure_id_frame: MeasureIDFrame

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        match node:
            case SetObservable():
                return self.rewrite_SetObservable(node)
            case _:
                return RewriteResult()

    def rewrite_SetObservable(self, node: SetObservable) -> RewriteResult:
        measure_ids = self.measure_id_frame.entries[node.measurements]
        assert isinstance(measure_ids, MeasureIdTuple)

        get_record_list = insert_get_records(
            node, measure_ids, self.measure_id_frame.num_measures_at_stmt[node]
        )

        observable_include_stmt = ObservableInclude(
            idx=node.idx, targets=tuple(get_record_list)
        )

        node.replace_by(observable_include_stmt)

        return RewriteResult(has_done_something=True)
