from bloqade.stim.parse import loads

from .base import codegen


def test_spp():
    mt = loads("SPP X1*!Y2 !Z1*Z2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "SPP X1*!Y2 !Z1*Z2"

    mt = loads("SPP_DAG X1*!Y2 !Z1*Z2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "SPP_DAG X1*!Y2 !Z1*Z2"
