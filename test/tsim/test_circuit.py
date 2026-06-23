import tsim
from bloqade import squin
from bloqade.tsim import Circuit
from bloqade.squin import kernel


def test_circuit():
    """Build a tsim.Circuit from a squin kernel."""

    @kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.t(q[0])
        squin.cx(q[0], q[1])

    circuit = Circuit(main)
    assert isinstance(circuit, tsim.Circuit)
    assert str(circuit) == "H 0\nT 0\nCX 0 1"


def test_circuit_insert_ticks():
    """insert_ticks=True separates operations with TICKs in the lowered circuit."""

    @kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])

    circuit = Circuit(main, insert_ticks=True)
    assert isinstance(circuit, tsim.Circuit)
    assert str(circuit) == "H 0\nTICK\nCX 0 1\nTICK"


def test_circuit_from_string():
    """Build a tsim.Circuit directly from a STIM program string."""
    program_text = "H 0\nT 0\nCX 0 1"

    circuit = Circuit(program_text)
    assert isinstance(circuit, tsim.Circuit)
    assert str(circuit) == program_text


def test_circuit_from_string_matches_native():
    """A string-initialized Circuit matches the native tsim.Circuit."""
    program_text = "H 0\nT 0\nCX 0 1"

    assert str(Circuit(program_text)) == str(tsim.Circuit(program_text))
