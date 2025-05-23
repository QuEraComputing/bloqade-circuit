import pytest
from kirin import ir

from bloqade.stim.emit import EmitStimMain
from bloqade.stim.parse import loads

emit = EmitStimMain()


def codegen(mt: ir.Method):
    # method should not have any arguments!
    emit.initialize()
    emit.run(mt=mt, args=())
    return emit.get_output()


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
