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


def test_circuit_with_leakage():
    @kernel
    def main():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.qubit_leakage(0.1, 0.1, q[0])
        squin.broadcast.qubit_leakage(0.2, 0.2, q)

    circuit = Circuit(main)
    assert isinstance(circuit, stim.Circuit)
    assert (
        str(circuit)
        == "X 0\nI_ERROR[leakage](0.1, 0.1) 0\nI_ERROR[leakage](0.2, 0.2) 0 1"
    )
