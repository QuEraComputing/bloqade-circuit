from typing import cast

from kirin import ir, interp

from bloqade.squin import op

from .lattice import (
    NoSites,
    HasNSites,
)
from .analysis import NSitesAnalysis


@op.dialect.register(key="op.nsites")
class SquinOp(interp.MethodTable):

    @interp.impl(op.stmts.Kron)
    def kron(self, interp: NSitesAnalysis, frame: interp.Frame, stmt: op.stmts.Kron):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        if isinstance(lhs, HasNSites) and isinstance(rhs, HasNSites):
            new_n_sites = lhs.sites + rhs.sites
            return (HasNSites(sites=new_n_sites),)
        else:
            return (NoSites(),)

    @interp.impl(op.stmts.Mult)
    def mult(self, interp: NSitesAnalysis, frame: interp.Frame, stmt: op.stmts.Mult):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)

        if isinstance(lhs, HasNSites) and isinstance(rhs, HasNSites):
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
                return (HasNSites(sites=lhs_sites + rhs_sites),)
        else:
            return (NoSites(),)

    @interp.impl(op.stmts.Control)
    def control(
        self, interp: NSitesAnalysis, frame: interp.Frame, stmt: op.stmts.Control
    ):
        op_sites = frame.get(stmt.op)

        if isinstance(op_sites, HasNSites):
            n_sites = op_sites.sites
            n_controls_attr = stmt.get_attr_or_prop("n_controls")
            n_controls = cast(ir.PyAttr[int], n_controls_attr).data
            return (HasNSites(sites=n_sites + n_controls),)
        else:
            return (NoSites(),)

    @interp.impl(op.stmts.Rot)
    def rot(self, interp: NSitesAnalysis, frame: interp.Frame, stmt: op.stmts.Rot):
        op_sites = frame.get(stmt.axis)
        return (op_sites,)

    @interp.impl(op.stmts.Scale)
    def scale(self, interp: NSitesAnalysis, frame: interp.Frame, stmt: op.stmts.Scale):
        op_sites = frame.get(stmt.op)
        return (op_sites,)
