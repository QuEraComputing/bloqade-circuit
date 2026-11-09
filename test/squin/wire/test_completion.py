"""Check complete conversion before independent wire ownership validation."""

import pytest
from kirin import ir
from kirin.ir.exception import ValidationErrorGroup

from bloqade import squin
from bloqade.squin.emit.wire import EmitWire
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.analysis.validation.wire import WireValidation, RegisterValidation
from bloqade.squin.analysis.validation.wire.target import ConversionTarget


@squin.kernel
def uncertain_operands(index: int):
    qs = squin.qalloc(2)
    squin.cx(qs[0], qs[index])


@squin.kernel
def identical_operands():
    qs = squin.qalloc(2)
    squin.cx(qs[0], qs[0])


def test_conversion_builds_wire_operations_and_validation_rejects_invalid_borrows():
    reason = "already out of its register"
    before = identical_operands.code.print_str()
    method = identical_operands.similar()
    method = EmitWire(method.dialects, method, {}).emit_method()
    assert not ConversionTarget.check(method)
    method.verify()
    method.verify_type()
    assert any(reason in str(error) for error in RegisterValidation().run(method)[1])
    with pytest.raises(ValidationErrorGroup, match=reason):
        WireValidation().check(method)
    with pytest.raises(ValidationErrorGroup, match=reason):
        SquinToWire().emit(identical_operands)
    assert identical_operands.code.print_str() == before


def test_operands_that_can_differ_at_runtime_convert():
    WireValidation().check(SquinToWire().emit(uncertain_operands))


@squin.kernel
def call_identical_operands():
    identical_operands()


@pytest.mark.parametrize(
    "failure",
    [
        ir.ValidationError(identical_operands.code, "unsupported callee operation"),
        RuntimeError("compiler failure"),
        ValueError("invalid compiler state"),
    ],
)
def test_unexpected_callee_failures_do_not_request_inlining(monkeypatch, failure):
    from bloqade.squin.emit.wire import EmitWire

    run = EmitWire.emit_method
    attempts = []

    def fail_callee(emitter):
        attempts.append(emitter.source.sym_name)
        if emitter.source.sym_name == identical_operands.sym_name:
            raise failure
        return run(emitter)

    monkeypatch.setattr(EmitWire, "emit_method", fail_callee)
    with pytest.raises(type(failure)) as caught:
        SquinToWire().emit(call_identical_operands)
    assert caught.value is failure
    assert attempts == [identical_operands.sym_name]


def test_definite_callee_ownership_failure_stops_emission(monkeypatch):
    run = EmitWire.emit_method
    attempts = []

    def record(emitter):
        attempts.append(emitter.source.sym_name)
        return run(emitter)

    monkeypatch.setattr(EmitWire, "emit_method", record)
    with pytest.raises(ValidationErrorGroup, match="already out of its register"):
        SquinToWire().emit(call_identical_operands)
    assert attempts == [identical_operands.sym_name]


def test_callee_failure_keeps_the_original_condition_and_location():
    with pytest.raises(ValidationErrorGroup) as caught:
        SquinToWire().emit(call_identical_operands)
    assert caught.value.__cause__ is None
    assert caught.value.errors
    for error in caught.value.errors:
        assert error.node.source is not None
        assert error.source is not None
        assert error.source.lineno > 0
    assert any(
        "already out of its register" in str(error) for error in caught.value.errors
    )


def test_borrow_failure_points_to_the_source_call_and_preserves_source_metadata():
    import inspect
    from pathlib import Path

    source = [(node, repr(node.source)) for node in identical_operands.code.walk()]
    lines, start = inspect.getsourcelines(identical_operands.py_func)
    expected_line = start + next(
        i for i, line in enumerate(lines) if "squin.cx" in line
    )
    for _ in range(2):
        with pytest.raises(ValidationErrorGroup) as caught:
            SquinToWire().emit(identical_operands)
        errors = [
            error
            for error in caught.value.errors
            if "already out of its register" in str(error)
        ]
        assert errors
        for error in errors:
            assert error.source.file == str(Path(__file__).resolve())
            assert error.source.lineno + error.source.lineno_begin == expected_line
        assert [(node, repr(node.source)) for node, _ in source] == source
