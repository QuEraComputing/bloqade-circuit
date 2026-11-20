from kirin import interp
from kirin.analysis import ForwardFrame

from bloqade.squin.analysis.schedule import DagScheduleAnalysis

from .stmts import Reset, Measure
from ._dialect import dialect


@dialect.register(key="qasm2.schedule.dag")
class CoreSchedule(interp.MethodTable):
    """Track the qubits accessed by QASM2 core operations."""

    @interp.impl(Measure)
    @interp.impl(Reset)
    def measure_or_reset(
        self,
        analysis: DagScheduleAnalysis,
        frame: ForwardFrame,
        stmt: Measure | Reset,
    ):
        """Record dependencies on the measured or reset qubits."""
        analysis.update_dag(stmt, [stmt.qarg])
        return ()
