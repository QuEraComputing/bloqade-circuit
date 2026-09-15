"""This module holds the emission of the `jeff.wire` statements."""

from kirin import interp

from jeff import JeffOp, IntType, JeffValue, QubitType, QuregType
from bloqade.jeff.types import qureg_length
from bloqade.jeff.dialects import stmts

from .base import EmitJeff, JeffFrame


@stmts.wire.dialect.register(key="emit.jeff")
class _Wire(interp.MethodTable):
    """Emit the `jeff.wire` statements."""

    @interp.impl(stmts.Alloc)
    def alloc(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Alloc
    ) -> tuple[JeffValue, ...]:
        """Emit a qubit allocation."""
        op = frame.push(JeffOp("qubit", "alloc", [], [JeffValue(QubitType())]))
        return (op.outputs[0],)

    @interp.impl(stmts.Free)
    @interp.impl(stmts.FreeZero)
    def free(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Free | stmts.FreeZero
    ) -> tuple[JeffValue, ...]:
        """Emit the release of a qubit."""
        kind = "free" if isinstance(stmt, stmts.Free) else "freeZero"
        frame.push(JeffOp("qubit", kind, [frame.get(stmt.wire)], []))
        return ()

    @interp.impl(stmts.Reset)
    def reset(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Reset
    ) -> tuple[JeffValue, ...]:
        """Emit a qubit reset."""
        op = frame.push(
            JeffOp("qubit", "reset", [frame.get(stmt.wire)], [JeffValue(QubitType())])
        )
        return (op.outputs[0],)

    @interp.impl(stmts.MeasureNd)
    def measure_nd(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.MeasureNd
    ) -> tuple[JeffValue, ...]:
        """Emit a measurement that keeps the qubit."""
        op = frame.push(
            JeffOp(
                "qubit",
                "measureNd",
                [frame.get(stmt.wire)],
                [JeffValue(QubitType()), JeffValue(IntType(1))],
            )
        )
        return (op.outputs[0], op.outputs[1])

    @interp.impl(stmts.Measure)
    def measure(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Measure
    ) -> tuple[JeffValue, ...]:
        """Emit a measurement that consumes the qubit."""
        op = frame.push(
            JeffOp("qubit", "measure", [frame.get(stmt.wire)], [JeffValue(IntType(1))])
        )
        return (op.outputs[0],)

    @interp.impl(stmts.RegCreate)
    def reg_create(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.RegCreate
    ) -> tuple[JeffValue, ...]:
        """Emit a register built from qubits."""
        wires = [frame.get(wire) for wire in stmt.wires]
        op = frame.push(
            JeffOp("qureg", "create", wires, [JeffValue(QuregType(len(wires)))])
        )
        return (op.outputs[0],)

    @interp.impl(stmts.RegAlloc)
    def reg_alloc(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.RegAlloc
    ) -> tuple[JeffValue, ...]:
        """Emit a register allocation."""
        op = frame.push(
            JeffOp(
                "qureg",
                "alloc",
                [frame.get(stmt.size)],
                [JeffValue(QuregType(qureg_length(stmt.result.type)))],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.RegFree)
    @interp.impl(stmts.RegFreeZero)
    def reg_free(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.RegFree | stmts.RegFreeZero
    ) -> tuple[JeffValue, ...]:
        """Emit the release of a register."""
        kind = "free" if isinstance(stmt, stmts.RegFree) else "freeZero"
        frame.push(JeffOp("qureg", kind, [frame.get(stmt.reg)], []))
        return ()

    @interp.impl(stmts.Extract)
    def extract(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Extract
    ) -> tuple[JeffValue, ...]:
        """Emit the extraction of one qubit from a register."""
        reg = frame.get(stmt.reg)
        op = frame.push(
            JeffOp(
                "qureg",
                "extractIndex",
                [reg, frame.get(stmt.index)],
                [JeffValue(reg.type), JeffValue(QubitType())],
            )
        )
        return (op.outputs[0], op.outputs[1])

    @interp.impl(stmts.Insert)
    def insert(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.Insert
    ) -> tuple[JeffValue, ...]:
        """Emit the insertion of one qubit into a register."""
        reg = frame.get(stmt.reg)
        op = frame.push(
            JeffOp(
                "qureg",
                "insertIndex",
                [reg, frame.get(stmt.index), frame.get(stmt.wire)],
                [JeffValue(reg.type)],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.ExtractSlice)
    def extract_slice(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.ExtractSlice
    ) -> tuple[JeffValue, ...]:
        """Emit the extraction of a slice from a register."""
        reg = frame.get(stmt.reg)
        op = frame.push(
            JeffOp(
                "qureg",
                "extractSlice",
                [reg, frame.get(stmt.start), frame.get(stmt.length)],
                [JeffValue(reg.type), JeffValue(QuregType(None))],
            )
        )
        return (op.outputs[0], op.outputs[1])

    @interp.impl(stmts.InsertSlice)
    def insert_slice(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.InsertSlice
    ) -> tuple[JeffValue, ...]:
        """Emit the insertion of a slice into a register."""
        reg = frame.get(stmt.reg)
        op = frame.push(
            JeffOp(
                "qureg",
                "insertSlice",
                [reg, frame.get(stmt.start), frame.get(stmt.slice_reg)],
                [JeffValue(reg.type)],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.RegSplit)
    def reg_split(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.RegSplit
    ) -> tuple[JeffValue, ...]:
        """Emit the split of a register into two registers."""
        op = frame.push(
            JeffOp(
                "qureg",
                "split",
                [frame.get(stmt.reg), frame.get(stmt.index)],
                [JeffValue(QuregType(None)), JeffValue(QuregType(None))],
            )
        )
        return (op.outputs[0], op.outputs[1])

    @interp.impl(stmts.RegJoin)
    def reg_join(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.RegJoin
    ) -> tuple[JeffValue, ...]:
        """Emit the join of two registers into one register."""
        op = frame.push(
            JeffOp(
                "qureg",
                "join",
                [frame.get(stmt.first), frame.get(stmt.second)],
                [JeffValue(QuregType(None))],
            )
        )
        return (op.outputs[0],)

    @interp.impl(stmts.RegLength)
    def reg_length(
        self, emit: EmitJeff, frame: JeffFrame, stmt: stmts.RegLength
    ) -> tuple[JeffValue, ...]:
        """Emit a query of the register length."""
        reg = frame.get(stmt.reg)
        op = frame.push(
            JeffOp(
                "qureg",
                "length",
                [reg],
                [JeffValue(reg.type), JeffValue(IntType(32))],
            )
        )
        return (op.outputs[0], op.outputs[1])
