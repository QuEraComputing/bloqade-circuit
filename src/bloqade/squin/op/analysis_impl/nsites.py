from kirin import interp

from bloqade.squin.analysis.nsites.lattice import NoSites, NumberSites
from bloqade.squin.analysis.nsites.analysis import NSitesAnalysis

from .. import stmts
from .._dialect import dialect


@dialect.register(key="op.nsites")
class SquinOpNSitesMethods(interp.MethodTable):

    @interp.impl(stmts.Kron)
    def kron(self, interp: NSitesAnalysis, frame: interp.Frame, stmt: stmts.Kron):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        if isinstance(lhs, NumberSites) and isinstance(rhs, NumberSites):
            new_n_sites = lhs.sites + rhs.sites
            return (NumberSites(sites=new_n_sites),)
        else:
            return (NoSites(),)

    @interp.impl(stmts.Mult)
    def mult(self, interp: NSitesAnalysis, frame: interp.Frame, stmt: stmts.Mult):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)

        if isinstance(lhs, NumberSites) and isinstance(rhs, NumberSites):
            lhs_sites = lhs.sites
            rhs_sites = rhs.sites
            # I originally considered throwing an exception here
            # but Xiu-zhe (Roger) Luo has pointed out it would be
            # a much better UX to add a type element that
            # could explicitly indicate the error. The downside
            # is you'll have some added complexity in the type lattice.
            if lhs_sites != rhs_sites:
                return (NoSites(),)
            else:
                return (NumberSites(sites=lhs_sites + rhs_sites),)
        else:
            return (NoSites(),)

    @interp.impl(stmts.Control)
    def control(self, interp: NSitesAnalysis, frame: interp.Frame, stmt: stmts.Control):
        op_sites = frame.get(stmt.op)

        if isinstance(op_sites, NumberSites):
            n_sites = op_sites.sites
            return (NumberSites(sites=n_sites + stmt.n_controls),)
        else:
            return (NoSites(),)

    @interp.impl(stmts.Rot)
    def rot(self, interp: NSitesAnalysis, frame: interp.Frame, stmt: stmts.Rot):
        op_sites = frame.get(stmt.axis)
        return (op_sites,)

    @interp.impl(stmts.Scale)
    def scale(self, interp: NSitesAnalysis, frame: interp.Frame, stmt: stmts.Scale):
        op_sites = frame.get(stmt.op)
        return (op_sites,)
