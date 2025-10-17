from abc import abstractmethod
from dataclasses import dataclass

from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.print.printer import Printer

from bloqade.squin import qubit
from bloqade.analysis.address import Address


@qubit.dialect.register
@dataclass
class AddressAttribute(ir.Attribute):

    name = "Address"
    address: Address

    def __hash__(self) -> int:
        return hash(self.address)

    def print_impl(self, printer: Printer) -> None:
        # Can return to implementing this later
        printer.print(self.address)


@dataclass
class WrapAnalysis(RewriteRule):

    @abstractmethod
    def wrap(self, value: ir.SSAValue) -> bool:
        pass

    def rewrite_Block(self, node: ir.Block) -> RewriteResult:
        has_done_something = any(self.wrap(arg) for arg in node.args)
        return RewriteResult(has_done_something=has_done_something)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        has_done_something = any(self.wrap(result) for result in node.results)
        return RewriteResult(has_done_something=has_done_something)


@dataclass
class WrapAddressAnalysis(WrapAnalysis):
    address_analysis: dict[ir.SSAValue, Address]

    def wrap(self, value: ir.SSAValue) -> bool:
        if (address_analysis_result := self.address_analysis.get(value)) is None:
            return False

        if value.hints.get("address") is not None:
            return False

        value.hints["address"] = AddressAttribute(address_analysis_result)

        return True
