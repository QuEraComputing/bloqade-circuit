import stim
from bloqade import squin
from bloqade.stim import Circuit
from bloqade.squin import kernel


def test_circuit():
    """Build a stim.Circuit from a squin kernel."""

    @kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])

    circuit = Circuit(main)
    assert isinstance(circuit, stim.Circuit)
    assert str(circuit) == "H 0\nCX 0 1"


def test_circuit_from_string():
    """Build a stim.Circuit directly from a STIM program string."""
    program_text = "H 0\nCX 0 1"

    circuit = Circuit(program_text)
    assert isinstance(circuit, stim.Circuit)
    assert str(circuit) == program_text


def test_circuit_from_string_matches_native():
    """A string-initialized Circuit matches the native stim.Circuit."""
    program_text = "H 0\nCX 0 1"

    assert str(Circuit(program_text)) == str(stim.Circuit(program_text))
