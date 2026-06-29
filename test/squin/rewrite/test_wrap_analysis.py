from kirin import ir, types

from bloqade.analysis import address
from bloqade.squin.rewrite.wrap_analysis import (
    WrapAnalysis,
    AddressAttribute,
    WrapAddressAnalysis,
)


class _TestStmt(ir.Statement):
    name = "test.stmt"


class DelegatingWrapAnalysis(WrapAnalysis):
    def wrap(self, value: ir.SSAValue) -> bool:
        return super().wrap(value)


class RecordingWrapAnalysis(WrapAnalysis):
    def __init__(self, wrapped_values: set[ir.SSAValue]):
        self.wrapped_values = wrapped_values
        self.seen_values: list[ir.SSAValue] = []

    def wrap(self, value: ir.SSAValue) -> bool:
        self.seen_values.append(value)
        return value in self.wrapped_values


def test_address_attribute_hashes_and_prints_wrapped_address():
    addr = address.AddressQubit(1)
    attribute = AddressAttribute(addr)
    printed_values = []

    class Printer:
        def print(self, value):
            printed_values.append(value)

    assert hash(attribute) == hash((type(addr), repr(addr)))

    attribute.print_impl(Printer())

    assert printed_values == [addr]


def test_wrap_analysis_default_wrap_does_not_change_value():
    value = ir.TestValue(type=types.Int)

    assert DelegatingWrapAnalysis().wrap(value) is False


def test_wrap_analysis_wraps_block_arguments():
    block = ir.Block(argtypes=[types.Int, types.Int])
    rule = RecordingWrapAnalysis({block.args[1]})

    result = rule.rewrite_Block(block)

    assert result.has_done_something is True
    assert rule.seen_values == list(block.args)


def test_wrap_analysis_wraps_statement_results():
    statement = _TestStmt(result_types=[types.Int, types.Int])
    rule = RecordingWrapAnalysis({statement.results[1]})

    result = rule.rewrite_Statement(statement)

    assert result.has_done_something is True
    assert rule.seen_values == list(statement.results)


def test_wrap_address_analysis_ignores_values_without_address_results():
    value = ir.TestValue(type=types.Int)
    rule = WrapAddressAnalysis({})

    assert rule.wrap(value) is False
    assert "address" not in value.hints


def test_wrap_address_analysis_ignores_existing_address_hints():
    value = ir.TestValue(type=types.Int)
    existing_attribute = AddressAttribute(address.AddressQubit(0))
    value.hints["address"] = existing_attribute
    rule = WrapAddressAnalysis({value: address.AddressQubit(1)})

    assert rule.wrap(value) is False
    assert value.hints["address"] is existing_attribute


def test_wrap_address_analysis_attaches_address_hint():
    value = ir.TestValue(type=types.Int)
    addr = address.AddressQubit(2)
    rule = WrapAddressAnalysis({value: addr})

    assert rule.wrap(value) is True
    assert value.hints["address"] == AddressAttribute(addr)
