from typing import Any
from dataclasses import field, dataclass

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.validation import ValidationPass
from kirin.analysis.forward import ForwardFrame

from bloqade.analysis.address import Address, AddressAnalysis


class _FlatKernelNoCloningAnalysis(Forward[EmptyLattice]):
    """Simple no-cloning validation for kernels that have been aggressively inlined."""

    keys = ("validate.nocloning.flatkernel",)
    lattice = EmptyLattice
    _address_frame: ForwardFrame[Address] | None = None

    def eval_fallback(
        self, frame: ForwardFrame[EmptyLattice], node: ir.Statement
    ) -> None:
        pass

    def run(self, method: ir.Method, *args: EmptyLattice, **kwargs: EmptyLattice):
        if self._address_frame is None:
            address_analysis = AddressAnalysis(method.dialects)
            address_frame, _ = address_analysis.run(method)
            self._address_frame = address_frame
        return super().run(method, *args, **kwargs)

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return EmptyLattice.bottom()

    def collect_errors(self, stmt: ir.Statement, addresses: list[int]):
        seen = set()
        duplicates = set()

        for addr in addresses:
            if addr in seen:
                duplicates.add(addr)
            else:
                seen.add(addr)

        self.add_validation_error(
            stmt,
            ir.ValidationError(
                stmt,
                f"Gate {stmt.name.upper()} applies to the qubits {duplicates} more than once.",
            ),
        )


@dataclass
class FlatKernelNoCloningValidation(ValidationPass):
    _analysis: _FlatKernelNoCloningAnalysis = field(init=False)

    def name(self) -> str:
        return "No-Cloning Validation"

    def get_required_analyses(self) -> list[type]:
        return [AddressAnalysis]

    def run(self, method: ir.Method) -> tuple[Any, list[ir.ValidationError]]:
        analysis = _FlatKernelNoCloningAnalysis(method.dialects)
        frame, _ = analysis.run(
            method, *(EmptyLattice.bottom() for _ in range(len(method.args) - 1))
        )

        self._analysis = analysis
        errors = analysis.get_validation_errors()

        return frame, errors
