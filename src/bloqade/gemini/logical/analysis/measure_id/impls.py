from kirin import interp
from kirin.analysis import forward
from kirin.dialects.ilist import IList

from bloqade.analysis.address.lattice import AddressReg
from bloqade.analysis.measure_id.lattice import (
    MeasureId,
    AnyMeasureId,
    RawMeasureId,
    MeasureIdTuple,
)
from bloqade.squin.rewrite.wrap_analysis import AddressAttribute

from ...dialects import operations
from .....analysis.measure_id import MeasurementIDAnalysis


@operations.dialect.register(key="measure_id")
class LogicalQubit(interp.MethodTable):
    @interp.impl(operations.stmts.TerminalLogicalMeasurement)
    def terminal_measurement(
        self,
        interp_: MeasurementIDAnalysis,
        frame: forward.ForwardFrame[MeasureId],
        stmt: operations.stmts.TerminalLogicalMeasurement,
    ):
        qubit_address_attr = stmt.qubits.hints.get("address")
        if not isinstance(qubit_address_attr, AddressAttribute):
            return (AnyMeasureId(),)

        qubit_address_result = qubit_address_attr.address
        print(qubit_address_result)
        if not isinstance(qubit_address_result, AddressReg):
            return (AnyMeasureId(),)

        num_physical_qubits = stmt.num_physical_qubits
        print(num_physical_qubits)
        if num_physical_qubits is None:
            return (AnyMeasureId(),)

        def logical_to_physical(
            logical_address: int,
        ):
            raw_measure_ids = map(
                RawMeasureId,
                range(
                    logical_address * num_physical_qubits,
                    (logical_address + 1) * num_physical_qubits,
                ),
            )
            return MeasureIdTuple(tuple(raw_measure_ids), IList)

        return (
            MeasureIdTuple(
                tuple(map(logical_to_physical, qubit_address_result.data)), IList
            ),
        )
