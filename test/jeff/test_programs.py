"""Test that programs from other compilers load, pass validation and re-emit."""

from pathlib import Path

import pytest
from kirin.ir.exception import ValidationErrorGroup

from bloqade import jeff
from bloqade.jeff import emit_jeff, load_jeff

from .build import validate

PROGRAMS = Path(__file__).parent / "programs"

REJECTED = {
    "incompatible_version": "does not support schema version 0.1.0",
    "invalid_entrypoint": "declaration without a body",
    "invalid_input_type": "Invalid type for wire, expected Wire, got int",
    "invalid_output_type": "Invalid type for result, expected Wire, got int",
    "isolation_violation": "region must be isolated",
    "linear_consumed_twice": "has 2 uses",
    "linear_never_consumed": "has 0 uses",
    "type_mismatch": "unsupported value type: int64",
    "used_before_defined": "used before it is defined",
    "value_out_of_bounds": "malformed jeff module",
    "value_produced_twice": "produced twice",
    "wrong_arity": "has 0 outputs. The statement expects 1.",
}
"""The files the jeff verifier rejects, each with the reason the loader
refuses it."""


@pytest.mark.parametrize("name", sorted(p.stem for p in PROGRAMS.glob("*.jeff")))
def test_loads_verifies_and_reemits(name):
    method = load_jeff(str(PROGRAMS / f"{name}.jeff"))
    validate(method)
    emit_jeff(method)


def test_every_rejected_file_has_a_test():
    assert sorted(p.stem for p in (PROGRAMS / "rejected").glob("*.jeff")) == sorted(
        REJECTED
    )


@pytest.mark.parametrize("name, message", sorted(REJECTED.items()))
def test_rejected_files_are_refused(name, message):
    with pytest.raises((jeff.JeffImportError, ValidationErrorGroup), match=message):
        load_jeff(str(PROGRAMS / "rejected" / f"{name}.jeff"))
