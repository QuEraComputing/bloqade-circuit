from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass

from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.print.printer import Printer

from bloqade import qubit
from bloqade.analysis.address import Address


@qubit.dialect.register
@dataclass
class AddressAttribute(ir.Attribute):
    """IR attribute carrying an address-analysis result."""

    name = "Address"

    address: Address

    def __hash__(self) -> int:
        """Return a hash based on the wrapped address."""

        return hash((type(self.address), repr(self.address)))

    def print_impl(self, printer: Printer) -> None:
        """Print the wrapped address."""

        printer.print(self.address)


@dataclass
class WrapAnalysis(RewriteRule):
    """Base rewrite rule that wraps analysis data onto SSA values."""

    @abstractmethod
    def wrap(self, value: ir.SSAValue) -> bool:
        """Wrap one SSA value and report whether it changed."""

        return False

    def rewrite_Block(self, node: ir.Block) -> RewriteResult:
        """Wrap block arguments."""

        has_done_something = any(self.wrap(arg) for arg in node.args)
        return RewriteResult(has_done_something=has_done_something)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Wrap statement results."""

        has_done_something = any(self.wrap(result) for result in node.results)
        return RewriteResult(has_done_something=has_done_something)


@dataclass
class WrapAddressAnalysis(WrapAnalysis):
    """Wrap address-analysis results into SSA value hints."""

    address_analysis: dict[ir.SSAValue, Address]

    def wrap(self, value: ir.SSAValue) -> bool:
        """Attach an address hint to a value when analysis produced one."""

        address_analysis_result = self.address_analysis.get(value)
        if address_analysis_result is None:
            return False

        if value.hints.get("address") is not None:
            return False

        value.hints["address"] = AddressAttribute(address_analysis_result)
        return True
