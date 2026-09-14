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
    if isinstance(node, SingleQubitGate):
        return _GateKind.SINGLE_QUBIT_GATE, 1
    elif isinstance(node, TwoQubitGate):
        return _GateKind.TWO_QUBIT_GATE, 1


@dataclass
class _CircuitDepthAnalysis(CountStatementAnalysis[_GateKind]):
    # TODO: replace CountStatementAnalysis directly?

    single_qubit_gate_threshold: int = 0
    two_qubit_gate_threshold: int = 0

    single_qubit_error_fired: bool = field(init=False, default=False)
    two_qubit_error_fired: bool = field(init=False, default=False)

    def initialize(self) -> Self:
        self.single_qubit_error_fired = False
        self.two_qubit_error_fired = False
        return super().initialize()

    def count_statement(self, node: ir.Statement) -> None:
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
    """
    NOTE: known limitations:
        * counts loop bodies once
        * counts both regions in IfElse
        * only checks single and two-qubit gates
    """

    # TODO: requiring arguments means we can't use it inside ValidationSuite because it hardcodes instantiation of validation passes without arguments; may need an upstream fix
    single_qubit_gate_threshold: int
    two_qubit_gate_threshold: int

    def name(self) -> str:
        """The name of the validation"""
        return "Circuit Depth Validation"

    def run(
        self, method: ir.Method
    ) -> tuple[ForwardFrame[EmptyLattice], list[ir.ValidationError]]:
        """Run the validation"""
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
