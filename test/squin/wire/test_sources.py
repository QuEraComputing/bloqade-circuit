"""Test the generic wire operations and the table that maps squin statements to them."""

import pytest
from kirin import ir, types

from bloqade.qubit import stmts as qubit_stmts
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.squin.wire import (
    Gate,
    Noise,
    GateKind,
    WireType,
    NoiseKind,
    RegisterGate,
    RegisterType,
    RegisterMeasure,
)
from bloqade.squin.noise import stmts as noise_stmts
from bloqade.native.dialects.gate import stmts as native_stmts
from bloqade.squin.rewrite.wire.sources import (
    ENTRIES,
    GATE_ENTRIES,
    NOISE_ENTRIES,
    GateEntry,
    NoiseEntry,
    check,
    entry_of,
)


def test_every_flat_qubit_statement_has_an_entry():
    for module in (gate_stmts, noise_stmts, native_stmts):
        for value in module.dialect.stmts:
            if value is noise_stmts.CorrelatedQubitLoss:
                continue
            assert value in ENTRIES, value.__name__
    assert noise_stmts.CorrelatedQubitLoss not in ENTRIES


def test_every_kind_has_exactly_one_source():
    assert set(GATE_ENTRIES) == set(GateKind)
    assert set(NOISE_ENTRIES) == set(NoiseKind)


def test_native_gates_keep_their_own_kinds():
    assert GATE_ENTRIES[GateKind.NATIVE_CZ] is ENTRIES[native_stmts.CZ]
    assert GATE_ENTRIES[GateKind.CZ] is ENTRIES[gate_stmts.CZ]
    assert ENTRIES[native_stmts.R].params == ("axis_angle", "rotation_angle")


def test_a_gate_continues_each_wire_in_order():
    control, target = (ir.TestValue(WireType) for _ in range(2))
    angle = ir.TestValue(types.Float)
    gate = Gate(GateKind.CX, (control, target))
    assert gate.linear == (control, target)
    assert gate.outputs == tuple(gate.results)
    assert gate.classical == ()
    assert entry_of(gate) is ENTRIES[gate_stmts.CX]
    rotation = Gate(GateKind.RZ, (control,), (angle,), adjoint=True)
    assert rotation.parameters == (angle,)
    assert rotation.adjoint is True


def test_a_register_operation_builds_its_scalar_form():
    registers = (ir.TestValue(RegisterType), ir.TestValue(RegisterType))
    gate = RegisterGate(GateKind.CZ, registers)
    wires = (ir.TestValue(WireType), ir.TestValue(WireType))
    scalar = gate.scalar(wires)
    assert isinstance(scalar, Gate) and scalar.kind is GateKind.CZ
    measure = RegisterMeasure(registers[0])
    assert measure.classical == (measure.bits,)


@pytest.mark.parametrize(
    "build",
    [
        lambda w: Gate(GateKind.CX, (w,)),
        lambda w: Gate(GateKind.RZ, (w,)),
        lambda w: Noise(NoiseKind.DEPOLARIZE2, (w, w)),
    ],
)
def test_an_operation_rejects_a_shape_that_differs_from_its_kind(build):
    with pytest.raises(ir.ValidationError, match="needs"):
        build(ir.TestValue(WireType)).verify()


@pytest.mark.parametrize(
    "entry, reason",
    [
        (GateEntry(gate_stmts.Rz, GateKind.CX), "counts of its kind"),
        (GateEntry(gate_stmts.CX, GateKind.X), "counts of its kind"),
        (
            NoiseEntry(noise_stmts.CorrelatedQubitLoss, NoiseKind.QUBIT_LOSS),
            "flat qubit lists",
        ),
    ],
)
def test_the_table_check_compares_each_entry_with_the_squin_schema(entry, reason):
    with pytest.raises(ValueError, match=reason):
        check(entry)


def test_an_entry_reads_its_fields_from_the_squin_schema():
    cx = ENTRIES[gate_stmts.CX]
    assert (cx.qubits, cx.params, cx.results) == (("controls", "targets"), (), ())
    assert ENTRIES[gate_stmts.U3].params == ("theta", "phi", "lam")
    assert ENTRIES[qubit_stmts.Measure].results == ("result",)


def test_an_entry_rebuilds_its_squin_statement():
    qubits = ir.TestValue(types.Any)
    made = ENTRIES[gate_stmts.T].build((qubits,), (), adjoint=True)
    assert isinstance(made, gate_stmts.T) and made.adjoint
    assert ENTRIES[gate_stmts.T].adjoint(made)
    assert not ENTRIES[gate_stmts.X].has_adjoint


def test_every_statement_that_continues_a_linear_operand_has_a_threads_trait():
    from bloqade.squin.wire import Threads, stmts, dialect

    ends = {
        stmts.Alloc,
        stmts.Free,
        stmts.AllocRegister,
        stmts.FreeRegister,
        stmts.PackRegister,
        stmts.SplitRegister,
        stmts.JoinRegister,
        stmts.DiscardRegister,
    }
    for value in dialect.stmts:
        assert (value.get_trait(Threads) is None) == (value in ends), value.__name__


def test_a_gate_takes_several_groups_of_its_kind():
    wires = tuple(ir.TestValue(WireType) for _ in range(4))
    gate = Gate(GateKind.CX, wires)
    gate.verify()
    assert gate.groups == (wires[:2], wires[2:])
    with pytest.raises(ir.ValidationError, match="per group"):
        Gate(GateKind.CX, wires[:3]).verify()
    with pytest.raises(ir.ValidationError, match="needs 1 register and"):
        RegisterGate(GateKind.X, (ir.TestValue(RegisterType),) * 2).verify()
