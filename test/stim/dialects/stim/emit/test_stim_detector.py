from bloqade import stim

from .base import codegen


def test_detector():

    @stim.main
    def test_simple_cx():
        stim.detector(coord=(1, 2, 3), targets=(stim.rec(-3), stim.rec(-1)))

    out = codegen(test_simple_cx)

    assert out.strip() == "DETECTOR(1, 2, 3) rec[-3] rec[-1]"


test_detector()
