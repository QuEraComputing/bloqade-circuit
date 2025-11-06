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
    _validation_errors: list[ValidationError] = field(default_factory=list, init=False)

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
        Returns Bottom, May, Must, or Top depending on what we can prove.
        """

        if not isinstance(stmt, func.Invoke):
            return tuple(Bottom() for _ in stmt.results)

        address_frame = self._address_frame
        if address_frame is None:
            return tuple(Top() for _ in stmt.results)

        concrete_addrs: list[int] = []
        has_unknown = False
        has_qubit_args = False
        unknown_arg_names: list[str] = []

        for arg in stmt.args:
            addr = address_frame.get(arg)
            match addr:
                case AddressQubit(data=qubit_addr):
                    has_qubit_args = True
                    concrete_addrs.append(qubit_addr)
                case AddressReg(data=addrs):
                    has_qubit_args = True
                    concrete_addrs.extend(addrs)
                case UnknownQubit() | UnknownReg() | Unknown():
                    has_qubit_args = True
                    has_unknown = True
                    arg_name = self._get_source_name(arg)
                    unknown_arg_names.append(arg_name)
                case _:
                    pass

        if not has_qubit_args:
            return tuple(Bottom() for _ in stmt.results)

        seen: set[int] = set()
        must_violations: list[str] = []
        gate_name = stmt.callee.sym_name.upper()

        for qubit_addr in concrete_addrs:
            if qubit_addr in seen:
                violation = self.format_violation(qubit_addr, gate_name)
                must_violations.append(violation)
                self._validation_errors.append(
                    QubitValidationError(stmt, qubit_addr, gate_name)
                )
            seen.add(qubit_addr)

        if must_violations:
            usage = Must(violations=frozenset(must_violations))
        elif has_unknown:
            args_str = " == ".join(unknown_arg_names)
            if len(unknown_arg_names) > 1:
                condition = f", when {args_str}"
            else:
                condition = f", with unknown argument {args_str}"

            self._validation_errors.append(
                PotentialQubitValidationError(stmt, gate_name, condition)
            )

            usage = May(violations=frozenset([f"{gate_name} Gate{condition}"]))
        else:
            usage = Bottom()

        return tuple(usage for _ in stmt.results) if stmt.results else (usage,)

    def _get_source_name(self, value: ir.SSAValue) -> str:
        """Trace back to get the source variable name for a value.

        For getitem operations like q[a], returns 'a'.
        For direct values, returns the value's name.
        """
        from kirin.dialects.py.indexing import GetItem

        if isinstance(value, ir.ResultValue) and isinstance(value.stmt, GetItem):
            index_arg = value.stmt.args[1]
            return self._get_source_name(index_arg)

        if isinstance(value, ir.BlockArgument):
            return value.name or f"arg{value.index}"

        if hasattr(value, "name") and value.name:
            return value.name

        return str(value)

    def run_method(
        self, method: ir.Method, args: tuple[QubitValidation, ...]
    ) -> tuple[ForwardFrame[QubitValidation], QubitValidation]:
        self_mt = self.method_self(method)
        return self.run_callable(method.code, (self_mt,) + args)

    def raise_validation_errors(self):
        """Raise validation errors for both definite and potential violations.
        Points to source file and line with snippet.
        """
        if not self._validation_errors:
            return

        # Print all errors with snippets
        for err in self._validation_errors:
            err.attach(self.method)

            # Format error message based on type
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

        raise
