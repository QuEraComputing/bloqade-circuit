# from typing import cast

from kirin import ir
from kirin.analysis import Forward
from kirin.analysis.forward import ForwardFrame

from bloqade.squin.op.types import OpType
from bloqade.squin.op.traits import Sites, HasNSitesTrait

from .lattice import NSites, NoSites, HasNSites


class NSitesAnalysis(Forward[NSites]):

    keys = ["op.nsites"]
    lattice = NSites

    # Take a page from const prop in Kirin,
    # I can get the data I want from the SizedTrait
    # and go from there

    ## This gets called before the registry look up
    def eval_stmt(self, frame: ForwardFrame, stmt: ir.Statement):
        method = self.lookup_registry(frame, stmt)
        if method is not None:
            return method(self, frame, stmt)
        elif stmt.has_trait(HasNSitesTrait):
            has_n_sites_trait = stmt.get_trait(HasNSitesTrait)
            sites = has_n_sites_trait.get_sites(stmt)
            return (HasNSites(sites=sites),)
        elif stmt.has_trait(Sites):
            sites_trait = stmt.get_trait(Sites)
            return (HasNSites(sites=sites_trait.data),)
        else:
            return (NoSites(),)

    # For when no implementation is found for the statement
    def eval_stmt_fallback(
        self, frame: ForwardFrame[NSites], stmt: ir.Statement
    ) -> tuple[NSites, ...]:  # some form of Shape will go back into the frame
        return tuple(
            (
                self.lattice.top()
                if result.type.is_subseteq(OpType)
                else self.lattice.bottom()
            )
            for result in stmt.results
        )

    def run_method(self, method: ir.Method, args: tuple[NSites, ...]):
        # NOTE: we do not support dynamic calls here, thus no need to propagate method object
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)
