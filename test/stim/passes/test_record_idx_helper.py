import io

from kirin import ir

from bloqade import stim, squin
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass
from bloqade.analysis.address import AddressAnalysis
from bloqade.record_idx_helper import (
    GetRecIdxFromPredicate,
    GetRecIdxFromMeasurement,
    dialect as record_idx_helper_dialect,
)
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.stim.passes.flatten import Flatten
from bloqade.analysis.measure_id.lattice import (
    RecId,
    Predicate,
)


def codegen(mt: ir.Method):
    buf = io.StringIO()
    emit = EmitStimMain(dialects=stim.main, io=buf)
    emit.initialize()
    emit.run(mt)
    return buf.getvalue().strip()


# ---------------------------------------------------------------------------
# RecId lattice element tests
# ---------------------------------------------------------------------------


def test_recid_subseteq_equal():
    rid_a = RecId(idx=-3, predicate=None)
    rid_b = RecId(idx=-3, predicate=None)
    assert rid_a.is_subseteq(rid_b)


def test_recid_subseteq_different_idx():
    rid_a = RecId(idx=-3, predicate=None)
    rid_b = RecId(idx=-4, predicate=None)
    assert not rid_a.is_subseteq(rid_b)


def test_recid_subseteq_different_predicate():
    rid_a = RecId(idx=-3, predicate=Predicate.IS_ONE)
    rid_b = RecId(idx=-3, predicate=None)
    assert not rid_a.is_subseteq(rid_b)


def test_recid_subseteq_same_predicate():
    rid_a = RecId(idx=-2, predicate=Predicate.IS_ONE)
    rid_b = RecId(idx=-2, predicate=Predicate.IS_ONE)
    assert rid_a.is_subseteq(rid_b)


def test_recid_join_equal():
    rid_a = RecId(idx=-3, predicate=None)
    rid_b = RecId(idx=-3, predicate=None)
    assert rid_a.join(rid_b) == rid_a


def test_recid_meet_equal():
    rid_a = RecId(idx=-3, predicate=None)
    rid_b = RecId(idx=-3, predicate=None)
    assert rid_a.meet(rid_b) == rid_a


# ---------------------------------------------------------------------------
# MeasureIDAnalysis tests for GetRecIdxFromMeasurement / GetRecIdxFromPredicate
# ---------------------------------------------------------------------------


def test_analysis_get_rec_idx_from_measurement_raw():
    @squin.kernel
    def test_kern():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        squin.set_detector([ms[0], ms[1]], coordinates=[0, 0])
        return

    Flatten(test_kern.dialects).fixpoint(test_kern)

    aa = AddressAnalysis(dialects=test_kern.dialects)
    af, _ = aa.run(test_kern)
    from kirin.rewrite import Walk
    from kirin.passes.hint_const import HintConst

    from bloqade.stim.rewrite import SetDetectorPartial
    from bloqade.squin.rewrite import WrapAddressAnalysis

    Walk(WrapAddressAnalysis(address_analysis=af.entries)).rewrite(test_kern.code)
    Walk(SetDetectorPartial()).rewrite(test_kern.code)

    analysis_dialects = test_kern.dialects.add(record_idx_helper_dialect)
    HintConst(analysis_dialects).unsafe_run(test_kern)

    mia = MeasurementIDAnalysis(dialects=analysis_dialects)
    frame, _ = mia.run(test_kern)

    rec_ids = [val for val in frame.entries.values() if isinstance(val, RecId)]

    assert len(rec_ids) == 2
    assert rec_ids[0] == RecId(idx=-3, predicate=None)
    assert rec_ids[1] == RecId(idx=-2, predicate=None)


def test_analysis_get_rec_idx_from_predicate():
    @squin.kernel
    def test_kern():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        if squin.is_one(ms[0]):
            squin.z(q[0])
        return

    Flatten(test_kern.dialects).fixpoint(test_kern)

    aa = AddressAnalysis(dialects=test_kern.dialects)
    af, _ = aa.run(test_kern)
    from kirin.rewrite import Walk
    from kirin.passes.hint_const import HintConst

    from bloqade.stim.rewrite import IfToStimPartial
    from bloqade.squin.rewrite import WrapAddressAnalysis

    Walk(WrapAddressAnalysis(address_analysis=af.entries)).rewrite(test_kern.code)
    Walk(IfToStimPartial()).rewrite(test_kern.code)

    analysis_dialects = test_kern.dialects.add(record_idx_helper_dialect)
    HintConst(analysis_dialects).unsafe_run(test_kern)

    mia = MeasurementIDAnalysis(dialects=analysis_dialects)
    frame, _ = mia.run(test_kern)

    rec_ids = [val for val in frame.entries.values() if isinstance(val, RecId)]

    assert len(rec_ids) == 1
    assert rec_ids[0] == RecId(idx=-3, predicate=Predicate.IS_ONE)


# ---------------------------------------------------------------------------
# Full pipeline tests using SquinToStimPass
# ---------------------------------------------------------------------------


def test_full_pipeline_detector_only():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        ms = squin.broadcast.measure(q)
        squin.set_detector([ms[0], ms[1]], coordinates=[0, 0])

    SquinToStimPass(main.dialects)(main)
    result = codegen(main)
    assert "DETECTOR(0, 0) rec[-2] rec[-1]" in result


def test_full_pipeline_observable_only():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        squin.set_observable(measurements=[ms[0]])

    SquinToStimPass(main.dialects)(main)
    result = codegen(main)
    assert "OBSERVABLE_INCLUDE(0) rec[-3]" in result


def test_full_pipeline_multiple_observables():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        squin.set_observable(measurements=[ms[0]])
        squin.set_observable(measurements=[ms[1]])

    SquinToStimPass(main.dialects)(main)
    result = codegen(main)
    assert "OBSERVABLE_INCLUDE(0) rec[-3]" in result
    assert "OBSERVABLE_INCLUDE(1) rec[-2]" in result


def test_full_pipeline_if_rewrite():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        ms = squin.broadcast.measure(q)
        if squin.is_one(ms[0]):
            squin.x(q[0])

    SquinToStimPass(main.dialects)(main)
    result = codegen(main)
    assert "CX rec[-2] 0" in result


def test_full_pipeline_if_multiple_paulis():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        if squin.is_one(ms[0]):
            squin.x(q[0])
            squin.y(q[1])
            squin.z(q[2])

    SquinToStimPass(main.dialects)(main)
    result = codegen(main)
    assert "CX rec[-3] 0" in result
    assert "CY rec[-3] 1" in result
    assert "CZ rec[-3] 2" in result


def test_full_pipeline_two_rounds_detectors():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        m0 = squin.broadcast.measure(q)
        squin.set_detector([m0[0]], coordinates=[0, 0])

        m1 = squin.broadcast.measure(q)
        squin.set_detector([m0[0], m1[0]], coordinates=[1, 1])

    SquinToStimPass(main.dialects)(main)
    result = codegen(main)
    lines = result.strip().split("\n")

    detector_lines = [line for line in lines if "DETECTOR" in line]
    assert len(detector_lines) == 2


def test_full_pipeline_complete():
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        ms = squin.broadcast.measure(q)

        if squin.is_one(ms[0]):
            squin.z(q[0])

        ms2 = squin.broadcast.measure(q)
        squin.set_detector([ms2[0], ms2[1]], coordinates=[0.0, 0.0])
        squin.set_observable(measurements=[ms2[2]])

    SquinToStimPass(main.dialects)(main)
    result = codegen(main)

    assert "H 0" in result
    assert "CX 0 1" in result
    assert "CZ rec[-4] 0" in result
    assert "DETECTOR" in result
    assert "OBSERVABLE_INCLUDE" in result


def test_full_pipeline_detector_back_references_earlier_measurements():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        m0 = squin.broadcast.measure(q)
        squin.set_detector([m0[0], m0[1]], coordinates=[0, 0])

        squin.broadcast.measure(q)
        squin.set_detector([m0[0], m0[1]], coordinates=[1, 1])

    SquinToStimPass(main.dialects)(main)
    result = codegen(main)

    detector_lines = [line.strip() for line in result.split("\n") if "DETECTOR" in line]
    assert len(detector_lines) == 2
    assert "DETECTOR(0, 0) rec[-2] rec[-1]" in detector_lines[0]
    assert "DETECTOR(1, 1) rec[-4] rec[-3]" in detector_lines[1]


def test_full_pipeline_no_leftover_helper_stmts():
    @squin.kernel
    def main():
        q = squin.qalloc(3)
        ms = squin.broadcast.measure(q)
        squin.set_detector([ms[0], ms[1]], coordinates=[0, 0])
        if squin.is_one(ms[2]):
            squin.x(q[0])

    SquinToStimPass(main.dialects)(main)

    for stmt in main.callable_region.stmts():
        assert not isinstance(stmt, GetRecIdxFromMeasurement)
        assert not isinstance(stmt, GetRecIdxFromPredicate)
