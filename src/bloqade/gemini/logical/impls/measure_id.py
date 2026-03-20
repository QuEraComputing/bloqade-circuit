from kirin import types as kirin_types, interp
from kirin.dialects import ilist

from bloqade.gemini.logical.dialects import operations
from bloqade.analysis.measure_id.lattice import (
    MeasureId,
    AnyMeasureId,
    RawMeasureId,
    MeasureIdTuple,
)
from bloqade.analysis.measure_id.analysis import MeasureIDFrame, MeasurementIDAnalysis


@operations.dialect.register(key="measure_id")
class LogicalQubit(interp.MethodTable):
    @interp.impl(operations.stmts.TerminalLogicalMeasurement)
    def terminal_measurement(
        self,
        interp_: MeasurementIDAnalysis,
        frame: MeasureIDFrame,
        stmt: operations.stmts.TerminalLogicalMeasurement,
    ):

        qubits_type = stmt.qubits.type
        if qubits_type.is_structurally_equal(kirin_types.Bottom):
            return (AnyMeasureId(),)

        assert isinstance(qubits_type, kirin_types.Generic)

        if not isinstance(len_var := qubits_type.vars[1], kirin_types.Literal):
            return (AnyMeasureId(),)

        if not isinstance(num_logical_qubits := len_var.data, int):
            return (AnyMeasureId(),)

        if (num_physical_qubits := stmt.num_physical_qubits) is not None:

            def logical_to_physical(
                logical_address: int,
            ) -> MeasureId:
                raw_measure_ids = map(
                    RawMeasureId,
                    range(
                        interp_.measure_count,
                        interp_.measure_count + num_physical_qubits,
                    ),
                )
                interp_.measure_count += num_physical_qubits
                return MeasureIdTuple(tuple(raw_measure_ids), ilist.IList)

        else:

            def logical_to_physical(
                logical_address: int,
            ) -> MeasureId:
                return AnyMeasureId()

        return (
            MeasureIdTuple(
                tuple(map(logical_to_physical, range(num_logical_qubits))), ilist.IList
            ),
        )
