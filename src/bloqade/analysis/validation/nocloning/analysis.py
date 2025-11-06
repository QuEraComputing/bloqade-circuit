from dataclasses import field

from kirin import ir
from kirin.analysis import Forward, TypeInference
from kirin.dialects import func
from kirin.ir.exception import ValidationError
from kirin.analysis.forward import ForwardFrame

from bloqade.analysis.address import (
    Address,
    AddressAnalysis,
)
from bloqade.analysis.address.lattice import AddressReg, AddressQubit

from .lattice import QubitValidation


class QubitValidationError(ValidationError):
    """ValidationError that records which qubit and gate caused the violation."""

    qubit_id: int
    gate_name: str

    def __init__(self, node: ir.IRNode, qubit_id: int, gate_name: str):
        # message stored in ValidationError so formatting/hint() will include it
        super().__init__(node, f"Qubit[{qubit_id}] cloned at {gate_name} gate.")
        self.qubit_id = qubit_id
        self.gate_name = gate_name


class NoCloningValidation(Forward[QubitValidation]):
    """
    Validates the no-cloning theorem by tracking qubit addresses.

    Built on top of AddressAnalysis to get qubit address information.
    """

    keys = ["validate.nocloning"]
    lattice = QubitValidation
    _address_frame: ForwardFrame[Address] = field(init=False)
    _type_frame: ForwardFrame = field(init=False)
    method: ir.Method
    _validation_errors: list[QubitValidationError] = field(
        default_factory=list, init=False
    )

    def __init__(self, mtd: ir.Method):
        """
        Input:
          - an ir.Method / kernel function
            infer dialects from it and remember method.
        """
        self.method = mtd
        super().__init__(mtd.dialects)

    def initialize(self):
        super().initialize()
        self._validation_errors = []
        address_analysis = AddressAnalysis(self.dialects)
        address_analysis.initialize()
        self._address_frame, _ = address_analysis.run_analysis(self.method)

        type_inference = TypeInference(self.dialects)
        type_inference.initialize()
        self._type_frame, _ = type_inference.run_analysis(self.method)

        return self

    def method_self(self, method: ir.Method) -> QubitValidation:
        return self.lattice.bottom()

    def get_qubit_addresses(self, addr: Address) -> frozenset[int]:
        """Extract concrete qubit addresses from an Address lattice element."""
        match addr:
            case AddressQubit(data=qubit_addr):
                return frozenset([qubit_addr])
            case AddressReg(data=addrs):
                return frozenset(addrs)
            case _:
                return frozenset()

    def format_violation(self, qubit_id: int, gate_name: str) -> str:
        """Return the violation string for a qubit + gate."""
        return f"Qubit[{qubit_id}] on {gate_name} Gate"

    def eval_stmt_fallback(
        self, frame: ForwardFrame[QubitValidation], stmt: ir.Statement
    ) -> tuple[QubitValidation, ...]:
        """
        Default statement evaluation: check for qubit usage violations.
        """

        if not isinstance(stmt, func.Invoke):
            return tuple(QubitValidation.bottom() for _ in stmt.results)

        address_frame = self._address_frame
        if address_frame is None:
            return tuple(QubitValidation.top() for _ in stmt.results)

        has_qubit_args = any(
            isinstance(address_frame.get(arg), (AddressQubit, AddressReg))
            for arg in stmt.args
        )

        if not has_qubit_args:
            return tuple(QubitValidation.bottom() for _ in stmt.results)

        used_addrs: list[int] = []
        for arg in stmt.args:
            addr = address_frame.get(arg)
            qubit_addrs = self.get_qubit_addresses(addr)
            used_addrs.extend(qubit_addrs)

        seen: set[int] = set()
        violations: list[str] = []

        for qubit_addr in used_addrs:
            if qubit_addr in seen:
                gate_name = stmt.callee.sym_name.upper()
                violations.append(self.format_violation(qubit_addr, gate_name))
                self._validation_errors.append(
                    QubitValidationError(stmt, qubit_addr, gate_name)
                )
            seen.add(qubit_addr)

        if not violations:
            return tuple(QubitValidation(violations=frozenset()) for _ in stmt.results)

        usage = QubitValidation(violations=frozenset(violations))
        return tuple(usage for _ in stmt.results) if stmt.results else (usage,)

    def run_method(
        self, method: ir.Method, args: tuple[QubitValidation, ...]
    ) -> tuple[ForwardFrame[QubitValidation], QubitValidation]:
        self_mt = self.method_self(method)
        return self.run_callable(method.code, (self_mt,) + args)

    def raise_validation_errors(self):
        """Raise validation error for each no-cloning violation found.
        Points to source file and line with snippet.
        """
        if not self._validation_errors:
            return

        # If multiple errors, print all with snippets first
        if len(self._validation_errors) > 1:
            for err in self._validation_errors:
                err.attach(self.method)
                # Print error message before snippet
                print(
                    f"\033[31mValidation Error\033[0m: Cloned qubit [{err.qubit_id}] at {err.gate_name} gate."
                )
                print(err.hint())
            print(f"Raised {len(self._validation_errors)} error(s).")
        raise
