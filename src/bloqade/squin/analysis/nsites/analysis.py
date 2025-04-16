# from typing import cast

from kirin import ir
from kirin.analysis import Forward
from kirin.analysis.forward import ForwardFrame

from bloqade.squin.op.types import OpType
from bloqade.squin.op.traits import HasSites, FixedSites

from .lattice import Sites, NoSites, NumberSites


class NSitesAnalysis(Forward[Sites]):

    keys = ["op.nsites"]
    lattice = Sites

    # Take a page from how constprop works in Kirin

    ## This gets called before the registry look up
    def eval_stmt(self, frame: ForwardFrame, stmt: ir.Statement):
        method = self.lookup_registry(frame, stmt)
        if method is not None:
            return method(self, frame, stmt)
        elif stmt.has_trait(HasSites):
            has_sites_trait = stmt.get_present_trait(HasSites)
            sites = has_sites_trait.get_sites(stmt)
            return (NumberSites(sites=sites),)
        elif stmt.has_trait(FixedSites):
            sites_trait = stmt.get_present_trait(FixedSites)
            return (NumberSites(sites=sites_trait.data),)
        else:
            return (NoSites(),)

    # For when no implementation is found for the statement
    def eval_stmt_fallback(
        self, frame: ForwardFrame[Sites], stmt: ir.Statement
    ) -> tuple[Sites, ...]:  # some form of Sites will go back into the frame
        return tuple(
            (
                self.lattice.top()
                if result.type.is_subseteq(OpType)
                else self.lattice.bottom()
            )
            for result in stmt.results
        )

    def run_method(self, method: ir.Method, args: tuple[Sites, ...]):
        # NOTE: we do not support dynamic calls here, thus no need to propagate method object
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)
