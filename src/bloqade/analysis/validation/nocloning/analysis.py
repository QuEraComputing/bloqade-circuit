from dataclasses import field

from kirin import ir
from kirin.analysis import Forward, TypeInference
from kirin.dialects import func
from kirin.analysis.forward import ForwardFrame

from bloqade.analysis.address import (
    Address,
    AddressReg,
    AddressQubit,
    AddressAnalysis,
)
from bloqade.analysis.address.lattice import QubitLike

from .lattice import QubitValidation


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
    violations: int = field(default=0, init=False)

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

    def get_stmt_info(self, stmt: ir.Statement) -> str:
        """String Report about the statement for violation messages."""
        if isinstance(stmt, func.Invoke) and hasattr(stmt, "callee"):
            gate_name = stmt.callee.sym_name.upper()
            return f"{gate_name} Gate"

        return f"{stmt.__class__.__name__}@{stmt}"

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
            isinstance(address_frame.get(arg), QubitLike) for arg in stmt.args
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
        stmt_info = self.get_stmt_info(stmt)

        for qubit_addr in used_addrs:
            if qubit_addr in seen:
                violations.append(f"Qubit[{qubit_addr}] at {stmt_info}")
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
