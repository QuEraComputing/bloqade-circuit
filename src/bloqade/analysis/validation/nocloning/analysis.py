from typing import Any

from kirin import ir
from kirin.analysis import Forward
from kirin.dialects import func
from kirin.ir.exception import ValidationError
from kirin.analysis.forward import ForwardFrame
from kirin.validation.validationpass import ValidationPass

from bloqade.analysis.address import (
    Address,
    AddressAnalysis,
)
from bloqade.analysis.address.lattice import (
    Unknown,
    AddressReg,
    UnknownReg,
    AddressQubit,
    PartialIList,
    PartialTuple,
    UnknownQubit,
)

from .lattice import May, Top, Must, Bottom, QubitValidation


class QubitValidationError(ValidationError):
    """ValidationError for definite (Must) violations with concrete qubit addresses."""

    qubit_id: int
    gate_name: str

    def __init__(self, node: ir.IRNode, qubit_id: int, gate_name: str):
        super().__init__(node, f"Qubit[{qubit_id}] cloned at {gate_name} gate.")
        self.qubit_id = qubit_id
        self.gate_name = gate_name


class PotentialQubitValidationError(ValidationError):
    """ValidationError for potential (May) violations with unknown addresses."""

    gate_name: str
    condition: str

    def __init__(self, node: ir.IRNode, gate_name: str, condition: str):
        super().__init__(node, f"Potential cloning at {gate_name} gate{condition}.")
        self.gate_name = gate_name
        self.condition = condition


class _NoCloningAnalysis(Forward[QubitValidation]):
    """Internal forward analysis for tracking qubit cloning violations."""

    keys = ("validate.nocloning",)
    lattice = QubitValidation

    def __init__(self, dialects):
        super().__init__(dialects)
        self._address_frame: ForwardFrame[Address] | None = None

    def method_self(self, method: ir.Method) -> QubitValidation:
        return self.lattice.bottom()

    def run(self, method: ir.Method, *args: QubitValidation, **kwargs: QubitValidation):
        if self._address_frame is None:
            addr_analysis = AddressAnalysis(self.dialects)
            addr_analysis.initialize()
            self._address_frame, _ = addr_analysis.run(method)
        return super().run(method, *args, **kwargs)

    def eval_fallback(
        self, frame: ForwardFrame[QubitValidation], node: ir.Statement
    ) -> tuple[QubitValidation, ...]:
        """Check for qubit usage violations and return lattice values."""
        if not isinstance(node, func.Invoke):
            return tuple(Bottom() for _ in node.results)

        address_frame = self._address_frame
        if address_frame is None:
            return tuple(Top() for _ in node.results)

        concrete_addrs: list[int] = []
        has_unknown = False
        has_qubit_args = False
        unknown_arg_names: list[str] = []

        for arg in node.args:
            addr = address_frame.get(arg)
            match addr:
                case AddressQubit(data=qubit_addr):
                    has_qubit_args = True
                    concrete_addrs.append(qubit_addr)
                case AddressReg(data=addrs):
                    has_qubit_args = True
                    concrete_addrs.extend(addrs)
                case (
                    UnknownQubit()
                    | UnknownReg()
                    | PartialIList()
                    | PartialTuple()
                    | Unknown()
                ):
                    has_qubit_args = True
                    has_unknown = True
                    arg_name = self._get_source_name(arg)
                    unknown_arg_names.append(arg_name)
                case _:
                    pass

        if not has_qubit_args:
            return tuple(Bottom() for _ in node.results)

        seen: set[int] = set()
        violations: set[tuple[int, str]] = set()
        s_name = getattr(node.callee, "sym_name", "<unknown>")
        gate_name = s_name.upper()

        for qubit_addr in concrete_addrs:
            if qubit_addr in seen:
                violations.add((qubit_addr, gate_name))
            seen.add(qubit_addr)

        if violations:
            usage = Must(violations=frozenset(violations))
        elif has_unknown:
            args_str = " == ".join(unknown_arg_names)
            if len(unknown_arg_names) > 1:
                condition = f", when {args_str}"
            else:
                condition = f", with unknown argument {args_str}"

            usage = May(violations=frozenset([(gate_name, condition)]))
        else:
            usage = Bottom()

        return tuple(usage for _ in node.results) if node.results else (usage,)

    def _get_source_name(self, value: ir.SSAValue) -> str:
        """Trace back to get the source variable name."""
        from kirin.dialects.py.indexing import GetItem

        if isinstance(value, ir.ResultValue) and isinstance(value.stmt, GetItem):
            index_arg = value.stmt.args[1]
            return self._get_source_name(index_arg)

        if isinstance(value, ir.BlockArgument):
            return value.name or f"arg{value.index}"

        if hasattr(value, "name") and value.name:
            return value.name

        return str(value)

    def extract_errors_from_frame(
        self, frame: ForwardFrame[QubitValidation]
    ) -> list[ValidationError]:
        """Extract validation errors from final lattice values.

        Only extracts errors from top-level statements (not nested in regions).
        """
        errors = []
        seen_statements = set()

        for node, value in frame.entries.items():
            if isinstance(node, ir.ResultValue):
                stmt = node.stmt
            elif isinstance(node, ir.Statement):
                stmt = node
            else:
                continue
            if stmt in seen_statements:
                continue
            seen_statements.add(stmt)
            if isinstance(value, Must):
                for qubit_id, gate_name in value.violations:
                    errors.append(QubitValidationError(stmt, qubit_id, gate_name))
            elif isinstance(value, May):
                for gate_name, condition in value.violations:
                    errors.append(
                        PotentialQubitValidationError(stmt, gate_name, condition)
                    )
        return errors

    def count_violations(self, frame: Any) -> int:
        """Count individual violations from the frame, same as test helper."""
        from .lattice import May, Must

        total = 0
        for node, value in frame.entries.items():
            if isinstance(value, Must):
                total += len(value.violations)
            elif isinstance(value, May):
                total += len(value.violations)
        return total


class NoCloningValidation(ValidationPass):
    """Validates the no-cloning theorem by tracking qubit addresses."""

    def __init__(self):
        self._analysis: _NoCloningAnalysis | None = None
        self._cached_address_frame = None

    def name(self) -> str:
        return "No-Cloning Validation"

    def get_required_analyses(self) -> list[type]:
        """Declare dependency on AddressAnalysis."""
        return [AddressAnalysis]

    def set_analysis_cache(self, cache: dict[type, Any]) -> None:
        """Use cached AddressAnalysis result."""
        self._cached_address_frame = cache.get(AddressAnalysis)

    def run(self, method: ir.Method) -> tuple[Any, list[ValidationError]]:
        """Run the no-cloning validation analysis."""
        if self._analysis is None:
            self._analysis = _NoCloningAnalysis(method.dialects)

        self._analysis.initialize()
        if self._cached_address_frame is not None:
            self._analysis._address_frame = self._cached_address_frame

        frame, _ = self._analysis.run(method)
        errors = self._analysis.extract_errors_from_frame(frame)

        return frame, errors

    def print_validation_errors(self):
        """Print all collected errors with formatted snippets."""
        if self._analysis is None:
            return

        if self._analysis.state._current_frame:
            frame = self._analysis.state._current_frame
            errors = self._analysis.extract_errors_from_frame(frame)

            for err in errors:
                if isinstance(err, QubitValidationError):
                    print(
                        f"\n\033[31mError\033[0m: Cloning qubit [{err.qubit_id}] at {err.gate_name} gate"
                    )
                elif isinstance(err, PotentialQubitValidationError):
                    print(
                        f"\n\033[33mWarning\033[0m: Potential cloning at {err.gate_name} gate{err.condition}"
                    )
                else:
                    print(
                        f"\n\033[31mError\033[0m: {err.args[0] if err.args else type(err).__name__}"
                    )
                print(err.hint())
