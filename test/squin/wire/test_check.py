from kirin import ir

from bloqade.squin import wire


def test_check_wired():

    qubit_1 = ir.TestValue()
    qubit_2 = ir.TestValue()
    op = ir.TestValue()

    body = ir.Region(block := ir.Block())

    wire_1 = block.args.append_from(wire.WireType)
    wire_2 = block.args.append_from(wire.WireType)

    block.stmts.append(wire.Apply(op, wire_1, wire_2))
    block.stmts.append(measure := wire.RegionMeasure(wire_1))
    block.stmts.append(wire.Yield(measure.result))

    wired = wire.Wired(
        body,
        qubit_1,
        qubit_2,
        memory_zone="test_zone",
    )

    wired.check()
