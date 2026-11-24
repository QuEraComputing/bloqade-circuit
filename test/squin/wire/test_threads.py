"""Check explicit operand and result mappings across different statement layouts."""

import pytest
from kirin import ir, types
from kirin.decl import info, statement

from bloqade.squin.wire import Gate, Threads, GateKind, WireType, Operation
from bloqade.squin.wire.traits import MatchesKind

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


class MixedRotationThreads(Threads["MixedRotation"]):
    """Continue the rotation's wire after its classical operand."""

    def threads(
        self, stmt: "MixedRotation"
    ) -> list[tuple[ir.SSAValue, ir.ResultValue]]:
        """Pair the input wire with its continued result."""
        return [(stmt.wire, stmt.wire_out)]


@statement(dialect=dialect)
class MixedRotation(Operation):
    """Place the rotation angle before the wire operand."""

    name = "mixed_rotation"
    traits = frozenset({MixedRotationThreads(), MatchesKind()})
    angle: ir.SSAValue = info.argument()
    wire: ir.SSAValue = info.argument(WireType)
    kind: GateKind = info.attribute()
    wire_out: ir.ResultValue = info.result(WireType)


def test_kind_validation_reads_parameters_by_the_wire_mapping() -> None:
    wire = ir.TestValue(WireType)
    rotation = MixedRotation(ir.TestValue(types.Float), wire, kind=GateKind.RZ)
    rotation.verify()
    rotation.verify_type()
    invalid = MixedRotation(ir.TestValue(types.String), wire, kind=GateKind.RZ)
    with pytest.raises(ir.ValidationError, match="Parameter 0"):
        invalid.verify_type()
