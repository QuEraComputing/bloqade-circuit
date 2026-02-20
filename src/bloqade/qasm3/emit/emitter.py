"""QASM3 string emitter.

Walks QASM3 dialect IR and produces OpenQASM 3.0 string output.
Handles qubit/bit declarations, all Supported_Gate_Set gates, measurement, and reset.
"""

import math
from dataclasses import dataclass, field

from kirin import ir
from kirin.dialects import func

from bloqade.qasm3.dialects.core import stmts as core_stmts
from bloqade.qasm3.dialects.uop import stmts as uop_stmts
from bloqade.qasm3.dialects.expr import stmts as expr_stmts


@dataclass
class QASM3Emitter:
    """Emit OpenQASM 3.0 strings from QASM3 dialect IR.

    Walks the IR statements in the entry block and produces
    standard OpenQASM 3.0 syntax.
    """

    # Maps SSA values to their string representations.
    # For registers: the register name (e.g. "q", "c")
    # For indexed qubits/bits: "q[0]", "c[1]"
    # For expressions: the expression string (e.g. "3.14", "pi", "pi/2")
    _ssa_names: dict[ir.SSAValue, str] = field(default_factory=dict, init=False)

    # Counter for generating unique register names when needed
    _qreg_count: int = field(default=0, init=False)
    _creg_count: int = field(default=0, init=False)

    def emit(self, entry: ir.Method) -> str:
        """Convert an ir.Method in QASM3 dialect to an OpenQASM 3.0 string.

        Args:
            entry: The IR method to emit. Must be in the QASM3 dialect.

        Returns:
            A syntactically valid OpenQASM 3.0 string.
        """
        self._ssa_names = {}
        self._qreg_count = 0
        self._creg_count = 0

        lines: list[str] = ["OPENQASM 3.0;", "include \"stdgates.inc\";", ""]

        block = entry.callable_region.blocks[0]
        for stmt in block.stmts:
            line = self._emit_stmt(stmt)
            if line is not None:
                lines.append(line)

        return "\n".join(lines) + "\n"

    def _emit_stmt(self, stmt: ir.Statement) -> str | None:
        """Emit a single IR statement as a QASM3 line. Returns None for skipped stmts."""
        # Core statements
        if isinstance(stmt, core_stmts.QRegNew):
            return self._emit_qreg_new(stmt)
        elif isinstance(stmt, core_stmts.BitRegNew):
            return self._emit_bitreg_new(stmt)
        elif isinstance(stmt, core_stmts.QRegGet):
            return self._emit_qreg_get(stmt)
        elif isinstance(stmt, core_stmts.BitRegGet):
            return self._emit_bitreg_get(stmt)
        elif isinstance(stmt, core_stmts.Measure):
            return self._emit_measure(stmt)
        elif isinstance(stmt, core_stmts.Reset):
            return self._emit_reset(stmt)

        # UOp gate statements
        elif isinstance(stmt, uop_stmts.UGate):
            return self._emit_ugate(stmt)
        elif isinstance(stmt, uop_stmts.RotationGate):
            return self._emit_rotation_gate(stmt)
        elif isinstance(stmt, uop_stmts.TwoQubitCtrlGate):
            return self._emit_two_qubit_gate(stmt)
        elif isinstance(stmt, uop_stmts.SingleQubitGate):
            return self._emit_single_qubit_gate(stmt)

        # Expression statements (tracked but don't produce output lines)
        elif isinstance(stmt, expr_stmts.ConstInt):
            self._ssa_names[stmt.result] = str(stmt.value)
            return None
        elif isinstance(stmt, expr_stmts.ConstFloat):
            return self._emit_const_float(stmt)
        elif isinstance(stmt, expr_stmts.ConstPI):
            self._ssa_names[stmt.result] = "pi"
            return None
        elif isinstance(stmt, expr_stmts.Neg):
            operand = self._resolve(stmt.value)
            self._ssa_names[stmt.result] = f"-{operand}"
            return None
        elif isinstance(stmt, expr_stmts.Add):
            self._ssa_names[stmt.result] = (
                f"({self._resolve(stmt.lhs)} + {self._resolve(stmt.rhs)})"
            )
            return None
        elif isinstance(stmt, expr_stmts.Sub):
            self._ssa_names[stmt.result] = (
                f"({self._resolve(stmt.lhs)} - {self._resolve(stmt.rhs)})"
            )
            return None
        elif isinstance(stmt, expr_stmts.Mul):
            self._ssa_names[stmt.result] = (
                f"({self._resolve(stmt.lhs)} * {self._resolve(stmt.rhs)})"
            )
            return None
        elif isinstance(stmt, expr_stmts.Div):
            self._ssa_names[stmt.result] = (
                f"({self._resolve(stmt.lhs)} / {self._resolve(stmt.rhs)})"
            )
            return None

        # func dialect statements (Return, ConstantNone, Function) — skip
        elif isinstance(stmt, (func.Return, func.ConstantNone, func.Function)):
            return None

        return None

    def _resolve(self, ssa: ir.SSAValue) -> str:
        """Resolve an SSA value to its string representation."""
        if ssa in self._ssa_names:
            return self._ssa_names[ssa]
        raise ValueError(f"Unresolved SSA value: {ssa}")

    # ---- Core statement emitters ----

    def _emit_qreg_new(self, stmt: core_stmts.QRegNew) -> str:
        size = self._get_int_value(stmt.n_qubits)
        name = f"q{self._qreg_count}" if self._qreg_count > 0 else "q"
        self._qreg_count += 1
        self._ssa_names[stmt.result] = name
        return f"qubit[{size}] {name};"

    def _emit_bitreg_new(self, stmt: core_stmts.BitRegNew) -> str:
        size = self._get_int_value(stmt.n_bits)
        name = f"c{self._creg_count}" if self._creg_count > 0 else "c"
        self._creg_count += 1
        self._ssa_names[stmt.result] = name
        return f"bit[{size}] {name};"

    def _emit_qreg_get(self, stmt: core_stmts.QRegGet) -> str | None:
        reg_name = self._resolve(stmt.reg)
        idx = self._get_int_value(stmt.idx)
        self._ssa_names[stmt.result] = f"{reg_name}[{idx}]"
        return None

    def _emit_bitreg_get(self, stmt: core_stmts.BitRegGet) -> str | None:
        reg_name = self._resolve(stmt.reg)
        idx = self._get_int_value(stmt.idx)
        self._ssa_names[stmt.result] = f"{reg_name}[{idx}]"
        return None

    def _emit_measure(self, stmt: core_stmts.Measure) -> str:
        qarg = self._resolve(stmt.qarg)
        carg = self._resolve(stmt.carg)
        return f"{carg} = measure {qarg};"

    def _emit_reset(self, stmt: core_stmts.Reset) -> str:
        qarg = self._resolve(stmt.qarg)
        return f"reset {qarg};"

    # ---- Gate emitters ----

    def _emit_single_qubit_gate(self, stmt: uop_stmts.SingleQubitGate) -> str:
        qarg = self._resolve(stmt.qarg)
        return f"{stmt.name} {qarg};"

    def _emit_rotation_gate(self, stmt: uop_stmts.RotationGate) -> str:
        theta = self._resolve(stmt.theta)
        qarg = self._resolve(stmt.qarg)
        return f"{stmt.name}({theta}) {qarg};"

    def _emit_two_qubit_gate(self, stmt: uop_stmts.TwoQubitCtrlGate) -> str:
        ctrl = self._resolve(stmt.ctrl)
        qarg = self._resolve(stmt.qarg)
        return f"{stmt.name} {ctrl}, {qarg};"

    def _emit_ugate(self, stmt: uop_stmts.UGate) -> str:
        theta = self._resolve(stmt.theta)
        phi = self._resolve(stmt.phi)
        lam = self._resolve(stmt.lam)
        qarg = self._resolve(stmt.qarg)
        return f"U({theta}, {phi}, {lam}) {qarg};"

    # ---- Expression helpers ----

    def _emit_const_float(self, stmt: expr_stmts.ConstFloat) -> None:
        value = stmt.value
        # Use clean representation for common values
        if value == math.pi:
            self._ssa_names[stmt.result] = "pi"
        elif value == -math.pi:
            self._ssa_names[stmt.result] = "-pi"
        else:
            self._ssa_names[stmt.result] = repr(value)
        return None

    def _get_int_value(self, ssa: ir.SSAValue) -> int:
        """Extract the integer value from an SSA value backed by a ConstInt."""
        owner = ssa.owner
        if isinstance(owner, expr_stmts.ConstInt):
            return owner.value
        # Try resolving from the name map and parsing
        name = self._resolve(ssa)
        return int(name)
