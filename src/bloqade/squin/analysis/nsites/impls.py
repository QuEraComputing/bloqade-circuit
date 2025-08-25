from kirin import ir, interp
from kirin.dialects import py, scf, func, ilist
from kirin.dialects.scf.typeinfer import TypeInfer as ScfTypeInfer

from bloqade.squin import op, wire, noise

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

    @interp.impl(op.stmts.PauliString)
    def pauli_string(
        self, interp: NSitesAnalysis, frame: interp.Frame, stmt: op.stmts.PauliString
    ):
        s = stmt.string
        return (NumberSites(sites=len(s)),)

    @interp.impl(op.stmts.Identity)
    def identity(
        self, interp: NSitesAnalysis, frame: interp.Frame, stmt: op.stmts.Identity
    ):
        sites = stmt.sites

        if not isinstance(sites, ir.ResultValue):
            return (interp.lattice.top(),)

        if not isinstance(site_stmt := sites.stmt, py.Constant):
            return (interp.lattice.top(),)

        if not isinstance(value := site_stmt.value, ir.PyAttr):
            return (interp.lattice.top(),)

        return (NumberSites(sites=value.data),)


@ilist.dialect.register(key="op.nsites")
class IListMethods(interp.MethodTable):

    @interp.impl(ilist.stmts.New)
    def new_list(
        self, interp: NSitesAnalysis, frame: interp.Frame, stmt: ilist.stmts.New
    ):
        return (tuple(frame.get(value) for value in stmt.values),)


@noise.dialect.register(key="op.nsites")
class NoiseOp(interp.MethodTable):

    @interp.impl(noise.stmts.Depolarize)
    @interp.impl(noise.stmts.SingleQubitPauliChannel)
    @interp.impl(noise.stmts.QubitLoss)
    def single_qubit_noise(
        self,
        interp: NSitesAnalysis,
        frame: interp.Frame,
        stmt: (
            noise.stmts.SingleQubitPauliChannel
            | noise.stmts.QubitLoss
            | noise.stmts.Depolarize
        ),
    ):
        return (NumberSites(sites=1),)

    @interp.impl(noise.stmts.Depolarize2)
    @interp.impl(noise.stmts.TwoQubitPauliChannel)
    def two_qubit_noise(
        self, interp: NSitesAnalysis, frame: interp.Frame, stmt: noise.stmts.Depolarize2
    ):
        return (NumberSites(sites=2),)

    @interp.impl(noise.stmts.PauliError)
    def pauli_error(
        self, interp: NSitesAnalysis, frame: interp.Frame, stmt: noise.stmts.PauliError
    ):
        pauli_ops_sites = frame.get(stmt.basis)
        return (pauli_ops_sites,)

    @interp.impl(noise.stmts.StochasticUnitaryChannel)
    def stochastic_unitary_noise(
        self,
        interp: NSitesAnalysis,
        frame: interp.Frame,
        stmt: noise.stmts.StochasticUnitaryChannel,
    ):
        ops = frame.get(stmt.operators)

        # StochasticUnitaryChannel always accepts an IList of Operators
        # but it's the number of sites of the individual operator themselves that should
        # represent the sites the channel acts on.
        if (
            isinstance(ops, tuple)
            and all(isinstance(op, NumberSites) for op in ops)
            and len(set([op.sites for op in ops])) == 1
        ):
            return (ops[0],)

        return (NoSites(),)


@scf.dialect.register(key="op.nsites")
class ScfSquinOp(ScfTypeInfer):
    pass


@func.dialect.register(key="op.nsites")
class FuncSquinOp(func.typeinfer.TypeInfer):
    pass
