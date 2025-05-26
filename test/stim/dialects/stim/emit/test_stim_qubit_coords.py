from bloqade import stim
from bloqade.stim.dialects import auxiliary

from .base import codegen


def test_qcoords():

    @stim.main
    def test_simple_qcoords():
        auxiliary.QubitCoordinates(coord=(0.1, 0.2), target=3)

    out = codegen(test_simple_qcoords)

    assert out.strip() == "QUBIT_COORDS(0.10000000, 0.20000000) 3"
