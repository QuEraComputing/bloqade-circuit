from dataclasses import dataclass

from kirin import ir, types as kirin_types
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.analysis.measure_id import MeasureIDFrame
from bloqade.stim.dialects.auxiliary import ObservableInclude
from bloqade.analysis.measure_id.lattice import (
    ObservableId,
    RawMeasureId,
    MeasureIdTuple,
)
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
        observable_id = self.measure_id_frame.entries.get(node.result, None)
        if observable_id is None or not isinstance(observable_id, ObservableId):
            return RewriteResult()

        measure_ids = observable_id.data
        if not isinstance(measure_ids, MeasureIdTuple):
            return RewriteResult()

        if not kirin_types.is_tuple_of(
            measure_ids_data := measure_ids.data, RawMeasureId
        ):
            return RewriteResult()

        get_record_list = insert_get_records(
            node, tuple_raw_measure_id=measure_ids_data
        )

        observable_include_stmt = ObservableInclude(
            idx=node.idx, targets=tuple(get_record_list)
        )

        node.replace_by(observable_include_stmt)

        return RewriteResult(has_done_something=True)
