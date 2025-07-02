from kirin import ir, lattice

from bloqade import squin
from bloqade.squin import wire
from bloqade.analysis import address
from bloqade.squin.analysis import nsites
from bloqade.analysis.layout import LayoutAnalysis


def test_qubit():

    @squin.kernel
    def test():
        q = squin.qubit.new(4)
        squin.qubit.apply(squin.op.cz(), q[0], q[1])

    addr_frame, _ = address.AddressAnalysis(test.dialects).run_analysis(test)
    nsites_frame, _ = nsites.NSitesAnalysis(test.dialects).run_analysis(test)

    analysis = LayoutAnalysis(test.dialects, addr_frame.entries, nsites_frame.entries)
    analysis.run_analysis(test, no_raise=False)

    assert analysis.stages == [((0, 1),)]


def test_wire():

    op = ir.TestValue()
    wire_1 = ir.TestValue()
    wire_2 = ir.TestValue()

    stmt = wire.Broadcast(op, wire_1, wire_2)

    address_analysis = {
        wire_1: address.AddressWire(address.AddressQubit(1)),
        wire_2: address.AddressWire(address.AddressQubit(2)),
    }
    nsites_analysis = {op: nsites.NumberSites(2)}

    analysis = LayoutAnalysis(squin.wired, address_analysis, nsites_analysis)

    analysis.initialize()
    analysis.run_stmt(
        stmt,
        (
            lattice.EmptyLattice.top(),
            lattice.EmptyLattice.top(),
            lattice.EmptyLattice.top(),
        ),
    )

    assert analysis.stages == [((1, 2),)]
