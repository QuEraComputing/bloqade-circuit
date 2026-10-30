"""DagScheduleAnalysis method-table implementations for the squin.gate dialect.

Lives under `squin.passes` (rather than `squin.gate`) so registration happens
after `bloqade.qasm2` has fully loaded — avoids a circular import with
`bloqade.squin.analysis.schedule`, which depends on `bloqade.qasm2.parse.print`.

Mirrors `bloqade.qasm2.dialects.uop.schedule.UOpSchedule`. Each gate stmt
carries its qubits as one ilist SSA value; `update_dag` follows the address
analysis (which returns `AddressReg` for the ilist) to identify the qubits
the stmt touches.
"""

from kirin import interp
from kirin.analysis import ForwardFrame

import bloqade.qasm2 as _qasm2  # noqa: F401  load qasm2 before analysis.schedule
from bloqade.squin.gate import stmts
from bloqade.squin.gate._dialect import dialect
from bloqade.squin.analysis.schedule import DagScheduleAnalysis


@dialect.register(key="qasm2.schedule.dag")
class SquinGateSchedule(interp.MethodTable):

    @interp.impl(stmts.X)
    @interp.impl(stmts.Y)
    @interp.impl(stmts.Z)
    @interp.impl(stmts.H)
    @interp.impl(stmts.T)
    @interp.impl(stmts.S)
    @interp.impl(stmts.SqrtX)
    @interp.impl(stmts.SqrtY)
    def single_qubit_gate(
        self,
        interp: DagScheduleAnalysis,
        frame: ForwardFrame,
        stmt: stmts.SingleQubitGate,
    ):
        interp.update_dag(stmt, [stmt.qubits])
        return ()

    @interp.impl(stmts.Rx)
    @interp.impl(stmts.Ry)
    @interp.impl(stmts.Rz)
    def rotation_gate(
        self,
        interp: DagScheduleAnalysis,
        frame: ForwardFrame,
        stmt: stmts.RotationGate,
    ):
        interp.update_dag(stmt, [stmt.qubits])
        return ()

    @interp.impl(stmts.U3)
    @interp.impl(stmts.PhasedXZ)
    def parameterized_single_qubit_gate(
        self,
        interp: DagScheduleAnalysis,
        frame: ForwardFrame,
        stmt: stmts.Gate,
    ):
        interp.update_dag(stmt, [stmt.qubits])
        return ()

    @interp.impl(stmts.CX)
    @interp.impl(stmts.CY)
    @interp.impl(stmts.CZ)
    def controlled_gate(
        self,
        interp: DagScheduleAnalysis,
        frame: ForwardFrame,
        stmt: stmts.ControlledGate,
    ):
        interp.update_dag(stmt, [stmt.controls, stmt.targets])
        return ()
