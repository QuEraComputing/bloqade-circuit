"""QASM3 target emitter.

Uses the EmitABC abstract-interpretation pattern (like the QASM2 emitter)
with dialect-registered method tables for dispatch.
"""

from dataclasses import field, dataclass

from kirin import ir
from kirin.rewrite import Walk

from bloqade.qasm3.groups import main as qasm3_main
from bloqade.qasm3.dialects.uop import _emit as _uop_emit  # noqa: F401

# Import dialect _emit modules to register method tables
from bloqade.qasm3.dialects.core import _emit as _core_emit  # noqa: F401
from bloqade.qasm3.dialects.expr import _emit as _expr_emit  # noqa: F401

from .main import EmitQASM3Main
from .rewrite import SquinQallocToQRegNew


@dataclass
class QASM3Emitter:
    """Emit OpenQASM 3.0 strings from QASM3 dialect IR.

    Uses abstract interpretation via EmitABC with method tables,
    following the same pattern as the QASM2 emitter.
    """

    include_files: list[str] = field(default_factory=lambda: ["stdgates.inc"])

    def emit(self, entry: ir.Method) -> str:
        """Convert an ir.Method in QASM3 dialect to an OpenQASM 3.0 string.

        Args:
            entry: The IR method to emit. Must be in the QASM3 dialect.

        Returns:
            A syntactically valid OpenQASM 3.0 string.
        """
        Walk(SquinQallocToQRegNew()).rewrite(entry.code)

        target_main = EmitQASM3Main(dialects=qasm3_main).initialize()

        # Merge interpreter registry entries from entry.dialects for any dialects
        # not in qasm3_main (e.g. py.constant, py.indexing from squin IR).
        # This avoids constructing a combined DialectGroup which would fail due to
        # duplicate lowering keys.
        extra_registry = entry.dialects.registry.interpreter(keys=target_main.keys)
        for sig, method in extra_registry.items():
            target_main.registry.setdefault(sig, method)

        target_main.run(entry)

        body = target_main.output
        assert body is not None, f"failed to emit {entry.sym_name}"

        # Build header
        header_lines: list[str] = ["OPENQASM 3.0;"]
        for inc in self.include_files:
            header_lines.append(f'include "{inc}";')
        header_lines.append("")

        return "\n".join(header_lines) + "\n" + body + "\n"
