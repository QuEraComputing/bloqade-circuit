import enum
from dataclasses import field, dataclass

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import ForwardFrame
from kirin.validation import ValidationPass
from typing_extensions import Self

from bloqade.squin import gate
from bloqade.analysis.count_statements import CountStatementAnalysis

SingleQubitGate = (
    gate.stmts.SingleQubitGate,
    gate.stmts.RotationGate,
    gate.stmts.U3,
    gate.stmts.PhasedXZ,
)

TwoQubitGate = (
    gate.stmts.TwoQubitGate,
    gate.stmts.ControlledGate,
)


class _GateKind(enum.Enum):
    SINGLE_QUBIT_GATE = enum.auto()
    TWO_QUBIT_GATE = enum.auto()


def _count_gates(node: ir.Statement):
    """Classify supported Squin gates into single- and two-qubit buckets."""
    if isinstance(node, SingleQubitGate):
        return _GateKind.SINGLE_QUBIT_GATE, 1
    elif isinstance(node, TwoQubitGate):
        return _GateKind.TWO_QUBIT_GATE, 1


@dataclass
class _CircuitDepthAnalysis(CountStatementAnalysis[_GateKind]):
    """Count supported gates and emit at most one error per exceeded threshold."""

    # TODO: replace CountStatementAnalysis directly?

    single_qubit_gate_threshold: int = 0
    two_qubit_gate_threshold: int = 0

    single_qubit_error_fired: bool = field(init=False, default=False)
    two_qubit_error_fired: bool = field(init=False, default=False)

    def initialize(self) -> Self:
        """Reset counts and threshold-error state for another analysis run."""
        self.single_qubit_error_fired = False
        self.two_qubit_error_fired = False
        return super().initialize()

    def count_statement(self, node: ir.Statement) -> None:
        """Count ``node`` and report any threshold crossed by this visit."""
        super().count_statement(node)

        single_count_exceeds_threshold = (
            self.counter[_GateKind.SINGLE_QUBIT_GATE] > self.single_qubit_gate_threshold
        )
        two_count_exceeds_threshold = (
            self.counter[_GateKind.TWO_QUBIT_GATE] > self.two_qubit_gate_threshold
        )

        trigger_single_qubit_gate_error = (
            single_count_exceeds_threshold and not self.single_qubit_error_fired
        )
        trigger_two_qubit_gate_error = (
            two_count_exceeds_threshold and not self.two_qubit_error_fired
        )

        if trigger_single_qubit_gate_error:
            self.add_validation_error(
                node,
                ir.ValidationError(
                    node,
                    f"Circuit too deep: a maximum of {self.single_qubit_gate_threshold} single-qubit gates is allowed.",
                ),
            )
            self.single_qubit_error_fired = True

        if trigger_two_qubit_gate_error:
            self.add_validation_error(
                node,
                ir.ValidationError(
                    node,
                    f"Circuit too deep: a maximum of {self.two_qubit_gate_threshold} two-qubit gates is allowed.",
                ),
            )
            self.two_qubit_error_fired = True


@dataclass
class FlatKernelCircuitDepthValidation(ValidationPass):
    """Validate static single- and two-qubit gate counts in reachable Squin IR.

    This pass counts supported gate statements rather than scheduling gates into
    parallel layers. A loop body contributes once regardless of trip count, and
    both regions of an ``scf.IfElse`` contribute. Other gate arities are ignored.

    Args:
        single_qubit_gate_threshold: Maximum allowed single-qubit gate count.
        two_qubit_gate_threshold: Maximum allowed two-qubit gate count.
    """

    # TODO: requiring arguments means we can't use it inside ValidationSuite because it hardcodes instantiation of validation passes without arguments; may need an upstream fix
    single_qubit_gate_threshold: int
    two_qubit_gate_threshold: int

    def name(self) -> str:
        """Return the human-readable validation name."""
        return "Circuit Depth Validation"

    def run(
        self, method: ir.Method
    ) -> tuple[ForwardFrame[EmptyLattice], list[ir.ValidationError]]:
        """Analyze ``method`` and return its final frame and validation errors."""
        analysis = _CircuitDepthAnalysis(
            method.dialects,
            predicate=_count_gates,
            single_qubit_gate_threshold=self.single_qubit_gate_threshold,
            two_qubit_gate_threshold=self.two_qubit_gate_threshold,
        )
        frame, _ = analysis.run(method)

        self._analysis = analysis
        errors = analysis.get_validation_errors()

        return frame, errors
