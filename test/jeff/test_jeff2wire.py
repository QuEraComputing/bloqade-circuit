"""Check direct Jeff conversion, ownership operations and the full wire round trip."""

import sys

import pytest
from kirin import ir, types
from kirin.dialects import py, func
from kirin.ir.exception import ValidationErrorGroup

from bloqade.jeff import JeffToWire, WireToJeff
from bloqade.squin.wire import stmts as wire, kernel as wire_kernel
from bloqade.squin.wire.types import RegisterType
from bloqade.squin.wire.ownership import mark_owned
from bloqade.squin.rewrite.wire.tools import reachable
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire import WireValidation
from bloqade.squin.analysis.validation.wire.target import ConversionTarget

from . import test_roundtrip as examples
from .helpers import simulate, roundtrips
from .test_roundtrip_squin import DETERMINISTIC_AFTER_THE_TRIP, _same, _plain


@pytest.fixture(autouse=True)
def no_reference_analysis(monkeypatch):
    class Guard:
        def find_spec(self, fullname, path=None, target=None):
            if fullname in {
                "bloqade.analysis.reference",
                "bloqade.squin.analysis.reference",
                "bloqade.jeff.analysis.wire",
            }:
                raise AssertionError(
                    "The complete round trip must use explicit wire values."
                )
            return None

    monkeypatch.setattr(sys, "meta_path", [Guard(), *sys.meta_path])


@pytest.mark.parametrize("kernel, args, expected", DETERMINISTIC_AFTER_THE_TRIP)
def test_every_stage_of_the_full_round_trip(kernel, args, expected):
    source = kernel.code.print_str()
    first = SquinToWire().emit(kernel)
    jeff = WireToJeff().emit(first)
    second = JeffToWire().emit(jeff)
    for method in reachable(second):
        assert not ConversionTarget.check(method)
        WireValidation().check(method)
    restored = WireToSquin().emit(second)
    assert _same(_plain(simulate(restored, *args)), expected)
    assert kernel.code.print_str() == source


@pytest.mark.parametrize(
    "build", [build for build in examples.KERNELS if build is not examples.rus]
)
def test_direct_jeff_import_can_emit_jeff_again(build):
    source = build()
    before = source.code.print_str()
    wired = JeffToWire().emit(source)
    assert not ConversionTarget.check(wired)
    assert roundtrips(WireToJeff().emit(wired))
    assert source.code.print_str() == before


def owned_register_method(*, borrow=False, duplicate=False):
    block = ir.Block(argtypes=(types.Any, RegisterType))
    register = block.args[1]
    at = py.Constant(0)
    take = (wire.Borrow if borrow else wire.Take)(register, at.result)
    block.stmts.extend([at, take, wire.Free(take.wire)])
    current = take.register_out
    if duplicate:
        again = wire.Take(current, at.result)
        block.stmts.extend([again, wire.Free(again.wire)])
        current = again.register_out
    none = func.ConstantNone()
    block.stmts.extend([wire.DiscardRegister(current), none, func.Return(none.result)])
    code = func.Function(
        sym_name="discard",
        body=ir.Region(block),
        signature=func.Signature(inputs=(RegisterType,), output=types.NoneType),
    )
    method = ir.Method(dialects=wire_kernel, code=code)
    mark_owned(method)
    return method


def test_owned_register_can_discard_moved_out_elements():
    WireValidation().check(owned_register_method())


@pytest.mark.parametrize("options", [{"borrow": True}, {"duplicate": True}])
def test_owned_functions_still_enforce_borrows_and_empty_elements(options):
    with pytest.raises(ValidationErrorGroup):
        WireValidation().check(owned_register_method(**options))


@pytest.mark.parametrize("n, expected", [(0, (1, 0)), (1, (0, 1)), (2, (1, 0))])
def test_owned_loop_can_exchange_its_state_positions(n, expected):
    from bloqade.jeff.dialects import stmts

    from .build import add, entry, method, for_loop

    block, _ = entry()
    a = add(block, stmts.Alloc()).result
    b = add(block, stmts.Alloc()).result
    a = add(block, stmts.Gate((a,), (), (), gate_name="x")).results[0]
    zero = add(block, stmts.ConstInt(value=0)).result
    count = add(block, stmts.ConstInt(value=n)).result
    one = add(block, stmts.ConstInt(value=1)).result
    loop = for_loop(block, zero, count, one, (a, b), lambda body, i, x, y: (y, x))
    first = add(block, stmts.Measure(loop.results[0])).bit
    second = add(block, stmts.Measure(loop.results[1])).bit
    source = method(
        block, (first, second), types.Generic(tuple, types.Bool, types.Bool)
    )
    restored = WireToSquin().emit(JeffToWire().emit(source))
    assert tuple(int(value) for value in simulate(restored)) == expected
