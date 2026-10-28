import pytest
from kirin import ir, types
from kirin.passes import TypeInfer
from kirin.rewrite import Walk, Chain, Fixpoint
from kirin.dialects import py, scf, func, ilist

from bloqade import squin
from bloqade.types import MeasurementResultType
from bloqade.qubit.stmts import IsOne, IsLost, IsZero, MeasurementPredicate
from bloqade.qubit.rewrite.measurement_if import RewriteMeasurementIfElse
from bloqade.qubit.rewrite.measurement_cmp import (
    RewriteMeasurementCmp as RewriteMeasurementCmp,
)
from bloqade.qubit.rewrite.measurement_boolean_ops import (
    RewriteMeasurementBooleanOps,
)


@ir.dialect_group(squin.kernel)
def kernel(self):
    """`squin.kernel` without the measurement desugaring, so the rules have work to do."""
    typeinfer_pass = TypeInfer(self)
    ilist_desugar_pass = ilist.IListDesugar(self)

    def run_pass(method: ir.Method):
        method.verify()
        typeinfer_pass(method)
        ilist_desugar_pass(method)
        typeinfer_pass(method)
        method.verify_type()

    return run_pass


def _apply(rule, mt: ir.Method):
    result = Walk(rule).rewrite(mt.code)
    mt.verify()
    TypeInfer(mt.dialects)(mt)
    mt.verify_type()
    return result


def _measurements(mt: ir.Method) -> list[ir.SSAValue]:
    return [
        stmt.result
        for stmt in mt.callable_region.walk()
        if isinstance(stmt, func.Invoke) and stmt.callee.sym_name == "measure"
    ]


def _returned(mt: ir.Method) -> list[ir.SSAValue]:
    ret = mt.callable_region.blocks[0].last_stmt
    assert isinstance(ret, func.Return)
    if isinstance(lst := ret.value.owner, ilist.New):
        return list(lst.values)
    return [ret.value]


def _predicate_of(value: ir.SSAValue) -> tuple[type, ir.SSAValue]:
    """Unpack `getitem(<predicate>(ilist.new([m])), 0)` into (predicate type, m)."""
    get = value.owner
    assert isinstance(get, py.GetItem)
    assert isinstance(idx := get.index.owner, py.Constant)
    assert idx.value.unwrap() == 0
    check = get.obj.owner
    assert isinstance(check, MeasurementPredicate)
    lst = check.measurements.owner
    assert isinstance(lst, ilist.New)
    assert len(lst.values) == 1
    return type(check), lst.values[0]


def _has_stmt(mt: ir.Method, stmt_type: type) -> bool:
    return any(isinstance(stmt, stmt_type) for stmt in mt.callable_region.walk())


# --- comparison -----------------------------------------------------------


@pytest.mark.parametrize(
    "value, predicate", [(0, IsZero), (1, IsOne), (2, IsLost), (True, IsOne)]
)
def test_cmp_eq_constant(value, predicate):
    @kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        return m == value

    result = _apply(RewriteMeasurementCmp(), main)

    assert result.has_done_something
    assert not _has_stmt(main, py.cmp.Eq)
    (ret,) = _returned(main)
    assert _predicate_of(ret) == (predicate, _measurements(main)[0])
    assert ret.type.is_subseteq(types.Bool)


def test_cmp_eq_constant_on_lhs():
    @kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        return 1 == m

    _apply(RewriteMeasurementCmp(), main)

    (ret,) = _returned(main)
    assert _predicate_of(ret) == (IsOne, _measurements(main)[0])


@pytest.mark.parametrize("value, predicate", [(0, IsZero), (1, IsOne), (2, IsLost)])
def test_cmp_not_eq_constant(value, predicate):
    @kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        return m != value

    result = _apply(RewriteMeasurementCmp(), main)

    assert result.has_done_something
    assert not _has_stmt(main, py.cmp.NotEq)
    (ret,) = _returned(main)
    assert isinstance(not_stmt := ret.owner, py.Not)
    assert _predicate_of(not_stmt.value) == (predicate, _measurements(main)[0])
    assert ret.type.is_subseteq(types.Bool)


def test_cmp_ignores_non_measurements():
    @kernel
    def main(x: int):
        return x == 1

    result = _apply(RewriteMeasurementCmp(), main)

    assert not result.has_done_something
    assert _has_stmt(main, py.cmp.Eq)
    assert not _has_stmt(main, MeasurementPredicate)


def test_cmp_ignores_unsupported_operands():
    @kernel
    def main(x: int):
        q = squin.qalloc(2)
        m = squin.measure(q[0])
        n = squin.measure(q[1])
        return [m == 5, m == x, m == n]

    result = _apply(RewriteMeasurementCmp(), main)

    assert not result.has_done_something
    assert all(isinstance(v.owner, py.cmp.Eq) for v in _returned(main))
    assert not _has_stmt(main, MeasurementPredicate)


# --- if/else --------------------------------------------------------------


def test_if_on_measurement():
    @kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m:
            squin.x(q[0])
        else:
            squin.y(q[0])
        return m

    result = _apply(RewriteMeasurementIfElse(), main)

    assert result.has_done_something
    (m,) = _measurements(main)
    (if_stmt,) = [s for s in main.callable_region.walk() if isinstance(s, scf.IfElse)]
    assert _predicate_of(if_stmt.cond) == (IsOne, m)

    for region in (if_stmt.then_body, if_stmt.else_body):
        (block,) = region.blocks
        assert not block.args[0].uses
        assert block.args[0].type.is_subseteq(types.Bool)
        assert isinstance(yield_stmt := block.last_stmt, scf.Yield)
        assert not yield_stmt.values

    assert not if_stmt.results
    assert _returned(main) == [m]
    assert main.return_type.is_subseteq(MeasurementResultType)


def test_if_ignores_non_measurements():
    @kernel
    def main(x: bool):
        q = squin.qalloc(1)
        if x:
            squin.x(q[0])

    result = _apply(RewriteMeasurementIfElse(), main)

    assert not result.has_done_something
    assert not _has_stmt(main, MeasurementPredicate)


def test_if_is_idempotent():
    @kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        if m:
            squin.x(q[0])

    _apply(RewriteMeasurementIfElse(), main)
    result = Walk(RewriteMeasurementIfElse()).rewrite(main.code)

    assert not result.has_done_something


# --- not / and / or -------------------------------------------------------


def test_not_measurement():
    @kernel
    def main():
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        return not m

    result = _apply(RewriteMeasurementBooleanOps(), main)

    assert result.has_done_something
    (ret,) = _returned(main)
    assert isinstance(not_stmt := ret.owner, py.Not)
    assert _predicate_of(not_stmt.value) == (IsOne, _measurements(main)[0])
    assert ret.type.is_subseteq(types.Bool)


@pytest.mark.parametrize("op", [py.And, py.Or])
def test_binary_both_measurements(op):
    if op is py.And:

        @kernel
        def main():
            q = squin.qalloc(2)
            m = squin.measure(q[0])
            n = squin.measure(q[1])
            return m and n

    else:

        @kernel
        def main():
            q = squin.qalloc(2)
            m = squin.measure(q[0])
            n = squin.measure(q[1])
            return m or n

    result = _apply(RewriteMeasurementBooleanOps(), main)

    assert result.has_done_something
    m, n = _measurements(main)
    (ret,) = _returned(main)
    assert isinstance(stmt := ret.owner, op)
    assert _predicate_of(stmt.lhs) == (IsOne, m)
    assert _predicate_of(stmt.rhs) == (IsOne, n)


def test_binary_mixed_operands():
    @kernel
    def main(x: bool):
        q = squin.qalloc(1)
        m = squin.measure(q[0])
        return [m and x, x or m]

    result = _apply(RewriteMeasurementBooleanOps(), main)

    assert result.has_done_something
    (m,) = _measurements(main)
    x = main.callable_region.blocks[0].args[1]
    and_stmt, or_stmt = (v.owner for v in _returned(main))

    assert isinstance(and_stmt, py.And)
    assert _predicate_of(and_stmt.lhs) == (IsOne, m)
    assert and_stmt.rhs is x

    assert isinstance(or_stmt, py.Or)
    assert or_stmt.lhs is x
    assert _predicate_of(or_stmt.rhs) == (IsOne, m)


def test_boolean_ops_ignore_non_measurements():
    @kernel
    def main(x: bool, y: bool):
        return [not x, x and y, x or y]

    result = _apply(RewriteMeasurementBooleanOps(), main)

    assert not result.has_done_something
    assert not _has_stmt(main, MeasurementPredicate)


# --- combined -------------------------------------------------------------


def test_all_rules_combined():
    @kernel
    def main():
        q = squin.qalloc(2)
        m = squin.measure(q[0])
        n = squin.measure(q[1])
        if m == 1:
            squin.x(q[1])
        if n:
            squin.x(q[0])
        return [not m, m != 0, m and n]

    rule = Chain(
        RewriteMeasurementCmp(),
        RewriteMeasurementIfElse(),
        RewriteMeasurementBooleanOps(),
    )
    Fixpoint(Walk(rule)).rewrite(main.code)
    main.verify()
    TypeInfer(main.dialects)(main)
    main.verify_type()

    for stmt in main.callable_region.walk():
        if isinstance(stmt, scf.IfElse):
            assert stmt.cond.type.is_subseteq(types.Bool)
        if isinstance(stmt, (py.cmp.Eq, py.cmp.NotEq, py.Not, py.And, py.Or)):
            assert not any(
                arg.type.is_subseteq(MeasurementResultType)
                and not arg.type.is_subseteq(types.Bottom)
                for arg in stmt.args
            )


def test_squin_kernel_desugars_measurement_booleans():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        m = squin.measure(q[0])
        n = squin.measure(q[1])
        if m == 1:
            squin.x(q[1])
        return [not m, m and n]

    assert _has_stmt(main, MeasurementPredicate)
    for stmt in main.callable_region.walk():
        if isinstance(stmt, (py.cmp.Eq, py.Not, py.And, scf.IfElse)):
            assert not any(
                arg.type.is_subseteq(MeasurementResultType)
                and not arg.type.is_subseteq(types.Bottom)
                for arg in stmt.args
            )
