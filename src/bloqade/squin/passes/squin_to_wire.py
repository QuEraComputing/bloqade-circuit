"""Emit complete wire IR directly from source squin methods."""

from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import TypeInfer
from kirin.rewrite import Walk, Fixpoint, DeadCodeElimination
from kirin.validation import ValidationSuite

from bloqade.squin.emit.wire import EmitWire
from bloqade.squin.wire.group import is_wire
from bloqade.squin.wire.errors import WireConversionError
from bloqade.squin.passes.wire_target import ConversionTarget
from bloqade.squin.emit.wire.functions import is_library
from bloqade.squin.rewrite.wire.driver import reachable
from bloqade.squin.analysis.validation.wire import (
    WireValidation,
    StructureValidation,
)


@dataclass
class SquinToWire:
    """Emit source methods once and require complete, validated wire results."""

    wire_dialects: tuple[ir.Dialect, ...] = ()
    """The dialects of the wire statements that other dialects emit, such as Gemini.

    A dialect outside squin adds its statements to wire programs with a method table
    under `emit.squin_wire`. Its wire statements need their dialect here.
    """
    converted: dict[ir.Method, ir.Method] = field(default_factory=dict, init=False)
    """The validated wire method of each converted source method."""

    def emit(self, method: ir.Method) -> ir.Method:
        """Build verified wire IR while preserving the source and its callees.

        `reachable` lists the user callees before their callers and rejects
        recursion. A library wrapper gets no conversion of its own, because
        `run_library` emits its body at each call.
        """
        self.converted = {}
        if is_wire(method):
            raise ValueError(
                "SquinToWire expects a squin kernel without wire statements."
            )
        for source in reachable(method, skip=is_library):
            ValidationSuite([StructureValidation]).validate(source).raise_if_invalid()
            self.converted[source] = self.emit_and_validate(source)
        return self.converted[method]

    def emit_and_validate(self, source: ir.Method) -> ir.Method:
        """Emit the wire method of `source`, infer its types and validate it.

        Dead-code removal runs first, so type inference reads only live operations.
        """
        method = EmitWire(
            source.dialects, source, self.converted, self.wire_dialects
        ).emit_method()
        Fixpoint(Walk(DeadCodeElimination())).rewrite(method.code)
        TypeInfer(method.dialects)(method)
        if violations := ConversionTarget.check(method):
            raise WireConversionError(
                f"'{method.sym_name}' violates the wire conversion target at: "
                + ", ".join(sorted(set(violations))),
                method.code,
            )
        WireValidation().check(method)
        return method
