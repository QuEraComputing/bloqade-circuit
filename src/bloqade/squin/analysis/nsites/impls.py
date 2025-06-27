from kirin import interp
from kirin.dialects import scf, func
from kirin.dialects.scf.typeinfer import TypeInfer as ScfTypeInfer

from bloqade.squin import op, wire

from .lattice import (
    NoSites,
    NumberSites,
)
from .analysis import NSitesAnalysis


@wire.dialect.register(key="op.nsites")
class SquinWire(interp.MethodTable):

    @interp.impl(wire.Apply)
    @interp.impl(wire.Broadcast)
    def apply(
        self,
        interp: NSitesAnalysis,
        frame: interp.Frame,
        stmt: wire.Apply | wire.Broadcast,
    ):

        return tuple(frame.get(input) for input in stmt.inputs)


@op.dialect.register(key="op.nsites")
class SquinOp(interp.MethodTable):

    @interp.impl(op.stmts.Kron)
    def kron(self, interp: NSitesAnalysis, frame: interp.Frame, stmt: op.stmts.Kron):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        if isinstance(lhs, NumberSites) and isinstance(rhs, NumberSites):
            new_n_sites = lhs.sites + rhs.sites
            return (NumberSites(sites=new_n_sites),)
        else:
            return (NoSites(),)

    @interp.impl(op.stmts.Mult)
    def mult(self, interp: NSitesAnalysis, frame: interp.Frame, stmt: op.stmts.Mult):
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

    @interp.impl(op.stmts.Control)
    def control(
        self, interp: NSitesAnalysis, frame: interp.Frame, stmt: op.stmts.Control
    ):
        op_sites = frame.get(stmt.op)

        if isinstance(op_sites, NumberSites):
            n_sites = op_sites.sites
            return (NumberSites(sites=n_sites + stmt.n_controls),)
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


@scf.dialect.register(key="op.nsites")
class ScfSquinOp(ScfTypeInfer):
    pass


@func.dialect.register(key="op.nsites")
class FuncSquinOp(func.typeinfer.TypeInfer):
    pass
