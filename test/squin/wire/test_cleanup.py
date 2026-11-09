"""Check complete emission of calls within nested loops and branches."""

import pytest
from test_roundtrip import simulate
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.types import Qubit
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin
from bloqade.squin.analysis.validation.wire.target import ConversionTarget


@squin.kernel
def kick(q: Qubit, count: int):
    for _ in range(count):
        squin.x(q)
    return count + 1


@squin.kernel
def branch_in_loop(n: int, flag: bool):
    qs = squin.qalloc(3)
    q = squin.qubit.new()
    total = 0
    for i in range(n):
        if flag:
            total = total + kick(qs[i], i)
            squin.x(q)
        else:
            for j in range(2):
                squin.cx(q, qs[j])
            total = total + kick(q, 1)
        squin.x(qs[2])
    return squin.broadcast.measure([qs[0], qs[1], qs[2], q]), total


@pytest.mark.parametrize("n", [0, 1, 2, 3])
@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.xfail(
    strict=True,
    raises=ValidationErrorGroup,
    reason="Requires the Kirin loop constant propagation backport: https://github.com/QuEraComputing/kirin/pull/760",
)
def test_nested_control_flow_emits_complete_wire_methods(n, flag):
    converter = SquinToWire()
    wired = converter.emit(branch_in_loop)
    assert all(
        ConversionTarget.check(method) == [] for method in converter.converted.values()
    )
    assert simulate(WireToSquin().emit(wired), n, flag) == simulate(
        branch_in_loop, n, flag
    )
