from typing import TypeVar
from dataclasses import field

from kirin import ir, interp
from kirin.analysis import Forward, const
from kirin.analysis.forward import ForwardFrame

from bloqade.types import QubitType

from .lattice import Address


class AddressAnalysis(Forward[Address]):
    """
    This analysis pass can be used to track the global addresses of qubits and wires.
    """

    keys = ("qubit.address",)
    lattice = Address
    next_address: int = field(init=False)

    def initialize(self):
        super().initialize()
        self.next_address: int = 0
        return self

    def method_self(self, method: ir.Method) -> Address:
        return self.lattice.bottom()

    def eval_fallback(
        self, frame: ForwardFrame[Address], node: ir.Statement
    ) -> interp.StatementResult[Address]:
        return tuple(
            (
                self.lattice.top()
                if result.type.is_subseteq(QubitType)
                else self.lattice.bottom()
            )
            for result in node.results
        )

    @property
    def qubit_count(self) -> int:
        """Total number of qubits found by the analysis."""
        return self.next_address
