import tsim
from bloqade import squin
from bloqade.tsim import Circuit
from bloqade.squin import kernel


def test_circuit():
    @kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.t(q[0])
        squin.cx(q[0], q[1])

    circuit = Circuit(main)
    assert isinstance(circuit, tsim.Circuit)
    assert str(circuit) == "H 0\nT 0\nCX 0 1"
