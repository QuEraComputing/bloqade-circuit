import stim
from bloqade import squin
from bloqade.stim import Circuit
from bloqade.squin import kernel


def test_circuit():
    @kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])

    circuit = Circuit(main)
    assert isinstance(circuit, stim.Circuit)
    assert str(circuit) == "H 0\nCX 0 1"
