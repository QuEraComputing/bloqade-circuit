from abc import abstractmethod
from dataclasses import dataclass

from kirin import ir
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.print.printer import Printer

from bloqade.squin import op, wire
from bloqade.analysis.address import Address
from bloqade.squin.analysis.nsites import Sites


@wire.dialect.register
@dataclass
class AddressAttribute(ir.Attribute):

    name = "Address"
    address: Address

    def __hash__(self) -> int:
        return hash(self.address)

    def print_impl(self, printer: Printer) -> None:
        # Can return to implementing this later
        printer.print(self.address)


@op.dialect.register
@dataclass
class SitesAttribute(ir.Attribute):

    name = "Sites"
    sites: Sites

    def __hash__(self) -> int:
        return hash(self.sites)

    def print_impl(self, printer: Printer) -> None:
        # Can return to implementing this later
        printer.print(self.sites)


@dataclass
class WrapAnalysis(RewriteRule):

    @abstractmethod
    def wrap(self, value: ir.SSAValue) -> bool:
        pass

    def rewrite_Block(self, node: ir.Block) -> RewriteResult:
        has_done_something = False
        for arg in node.args:
            if self.wrap(arg):
                has_done_something = True
        return RewriteResult(has_done_something=has_done_something)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        has_done_something = False
        for result in node.results:
            if self.wrap(result):
                has_done_something = True
        return RewriteResult(has_done_something=has_done_something)


@dataclass
class WrapAddressAnalysis(WrapAnalysis):
    address_analysis: dict[ir.SSAValue, Address]

    def wrap(self, value: ir.SSAValue) -> bool:
        address_analysis_result = self.address_analysis[value]

        if value.hints.get("address"):
            return False
        else:
            value.hints["address"] = AddressAttribute(address_analysis_result)

        return True


@dataclass
class WrapOpSiteAnalysis(WrapAnalysis):

    op_site_analysis: dict[ir.SSAValue, Sites]

    def wrap(self, value: ir.SSAValue) -> bool:
        op_site_analysis_result = self.op_site_analysis[value]

        if value.hints.get("sites"):
            return False
        else:
            value.hints["sites"] = SitesAttribute(op_site_analysis_result)

        return True
