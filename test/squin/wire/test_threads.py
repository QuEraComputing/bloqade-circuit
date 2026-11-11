"""Check explicit operand and result mappings across different statement layouts."""

import pytest
from kirin import ir, types
from kirin.decl import info, statement

from bloqade.squin.wire import Gate, Threads, GateKind, WireType, Operation

dialect = ir.Dialect("test.wire.threads")


class ReorderedThreads(Threads["Reordered"]):
    """Continue wires in the reverse order of the statement's wire results."""

    def threads(self, stmt: "Reordered") -> list[tuple[ir.SSAValue, ir.ResultValue]]:
        """Pair each input wire with its explicit result."""
        return [(stmt.first, stmt.last), (stmt.second, stmt.middle)]


@statement(dialect=dialect)
class Reordered(Operation):
    """Place a classical operand and result before the quantum values."""

    name = "reordered"
    traits = frozenset({ReorderedThreads()})
    angle: ir.SSAValue = info.argument(types.Float)
    first: ir.SSAValue = info.argument(WireType)
    second: ir.SSAValue = info.argument(WireType)
    number: ir.ResultValue = info.result(types.Int)
    middle: ir.ResultValue = info.result(WireType)
    last: ir.ResultValue = info.result(WireType)


def test_operation_accessors_follow_the_explicit_mapping() -> None:
    angle = ir.TestValue(types.Float)
    first, second = ir.TestValue(WireType), ir.TestValue(WireType)
    node = Reordered(angle, first, second)
    assert node.linear == (first, second)
    assert node.outputs == (node.last, node.middle)
    assert node.parameters == (angle,)
    assert node.classical == (node.number,)


def test_gate_mapping_rejects_a_missing_wire_result() -> None:
    first, second = ir.TestValue(WireType), ir.TestValue(WireType)
    malformed = Gate(GateKind.CX, (first, second))
    del malformed.results[1]
    with pytest.raises(ValueError, match="zip"):
        malformed.get_present_trait(Threads).threads(malformed)
