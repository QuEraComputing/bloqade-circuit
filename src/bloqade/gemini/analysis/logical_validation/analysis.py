from typing import Any
from dataclasses import field, dataclass

from kirin import ir
from kirin.interp import InterpreterError
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward, ForwardFrame
from kirin.validation import ValidationPass

from bloqade import squin
from bloqade.analysis.address import Address, AddressReg, AddressAnalysis


@dataclass
class _GeminiLogicalValidationAnalysis(Forward[EmptyLattice]):
    keys = ["gemini.validate.logical"]

    lattice = EmptyLattice
    addr_frame: ForwardFrame[Address]

    first_gates: dict[int, bool] = field(init=False, default_factory=dict)

    def eval_fallback(self, frame: ForwardFrame, node: ir.Statement):
        if isinstance(node, squin.gate.stmts.Gate):
            raise InterpreterError(f"Missing implementation for gate {node}")

        return tuple(self.lattice.bottom() for _ in range(len(node.results)))

    def check_first_gate(self, qubits: ir.SSAValue) -> bool:
        address = self.addr_frame.get(qubits)

        if not isinstance(address, AddressReg):
            # NOTE: we should have a flat kernel with simple address analysis, so in case we don't
            # get concrete addresses, we might as well error here since something's wrong
            return False

        is_first = True
        for addr_int in address.data:
            is_first = is_first and self.first_gates.get(addr_int, True)
            self.first_gates[addr_int] = False

        return is_first

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()


@dataclass
class GeminiLogicalValidation(ValidationPass):
    """Validates a logical gemini program"""

    def name(self) -> str:
        return "Gemini Logical Validation"

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        addr_frame, _ = AddressAnalysis(method.dialects).run(method)
        analysis = _GeminiLogicalValidationAnalysis(
            method.dialects, addr_frame=addr_frame
        )
        frame, _ = analysis.run(method)

        return frame, analysis.get_validation_errors()
