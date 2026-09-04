from dataclasses import field, dataclass

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import ForwardFrame
from kirin.validation import ValidationPass
from typing_extensions import Self

from bloqade.analysis.count_statements import CountStatementAnalysis


@dataclass
class _CircuitDepthAnalysis(CountStatementAnalysis):
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

        if (
            not self.single_qubit_error_fired
            and self.counts[0] > self.single_qubit_gate_threshold
        ):
            self.add_validation_error(
                node,
                ir.ValidationError(
                    node,
                    f"Circuit too deep: a maximum of {self.single_qubit_gate_threshold} single-qubit gates is allowed.",
                ),
            )
            self.single_qubit_error_fired = True

        if (
            not self.two_qubit_error_fired
            and self.counts[1] > self.two_qubit_gate_threshold
        ):
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

    # TODO: requiring arguments means we can't use it inside ValidatioNSuite because it hardcodes instantiation of validation passes without arguments; may need an upstream fix
    single_qubit_gate_threshold: int
    two_qubit_gate_threshold: int

    def name(self) -> str:
        """The name of the validation"""
        return "Circuit Depth Validation"

    def run(
        self, method: ir.Method
    ) -> tuple[ForwardFrame[EmptyLattice], list[ir.ValidationError]]:
        from bloqade.squin import gate

        def _count_single_and_two_qubit_gates(stmt: ir.Statement):
            if not isinstance(
                stmt,
                (
                    gate.stmts.SingleQubitGate,
                    gate.stmts.RotationGate,
                    gate.stmts.U3,
                    gate.stmts.PhasedXZ,
                    gate.stmts.TwoQubitGate,
                    gate.stmts.ControlledGate,
                ),
            ):
                return False, 0, 0

            idx = isinstance(stmt, (gate.stmts.TwoQubitGate, gate.stmts.ControlledGate))
            return True, idx, 1

        analysis = _CircuitDepthAnalysis(
            method.dialects,
            predicate=_count_single_and_two_qubit_gates,
            N=2,
            single_qubit_gate_threshold=self.single_qubit_gate_threshold,
            two_qubit_gate_threshold=self.two_qubit_gate_threshold,
        )
        frame, _ = analysis.run(method)

        self._analysis = analysis
        errors = analysis.get_validation_errors()

        return frame, errors
