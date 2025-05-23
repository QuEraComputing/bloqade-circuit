import pytest

from bloqade.stim.parse import loads

from .base import codegen


@pytest.mark.parametrize(
    "key,exp",
    [
        ("MX", "MX"),
        ("MY", "MY"),
        ("MZ", "MZ"),
        ("MXX", "MXX"),
        ("MYY", "MYY"),
        ("MZZ", "MZZ"),
        ("M", "MZ"),
    ],
)
def test_measures(key: str, exp: str):

    mt = loads(f"{key} 5 0 1 2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == f"{exp}(0.00000000) 5 0 1 2"

    mt = loads(f"{key}(0.2) 5 0 1 2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == f"{exp}(0.20000000) 5 0 1 2"


@pytest.mark.parametrize(
    "key,exp",
    [
        ("RX", "RX"),
        ("RY", "RY"),
        ("RZ", "RZ"),
        ("R", "RZ"),
    ],
)
def test_resets(key: str, exp: str):

    mt = loads(f"{key} 5 0 1 2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == f"{exp} 5 0 1 2"


def test_detector():
    mt = loads("DETECTOR rec[-1] rec[-9]")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "DETECTOR rec[-1] rec[-9]"

    mt = loads("DETECTOR(0.5,0.7) rec[-1] rec[-9]")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "DETECTOR(0.50000000, 0.70000000) rec[-1] rec[-9]"


def test_obs_include():
    mt = loads("OBSERVABLE_INCLUDE(3) rec[-1] rec[-9]")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "OBSERVABLE_INCLUDE(3) rec[-1] rec[-9]"


def test_tick():
    mt = loads("TICK")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "TICK"


def test_qcoords():
    mt = loads("QUBIT_COORDS(0.1,0.2) 3")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "QUBIT_COORDS(0.10000000, 0.20000000) 3"


def test_mpp():
    mt = loads("MPP !X1*Y2 Z1*Z2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "MPP(0.00000000) !X1*Y2 Z1*Z2"

    mt = loads("MPP(0.2) X1*!Y2 !Z1*Z2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "MPP(0.20000000) X1*!Y2 !Z1*Z2"
