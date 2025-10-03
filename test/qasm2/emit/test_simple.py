
from pathlib import Path
from bloqade.qasm2 import emit
from bloqade import qasm2

@qasm2.gate
def custom_gate(a: qasm2.Qubit, b: qasm2.Qubit):
    qasm2.cx(a, b)

@qasm2.main
def main():
    qreg = qasm2.qreg(4)
    creg = qasm2.creg(2)
    qasm2.cx(qreg[0], qreg[1])
    qasm2.reset(qreg[0])
    # qasm2.parallel.cz(ctrls=[qreg[0], qreg[1]], qargs=[qreg[2], qreg[3]])
    qasm2.measure(qreg[0], creg[0])
    if creg[0] == 1:
        qasm2.reset(qreg[1])
    custom_gate(qreg[0], qreg[1])

def test_simple(tmp_path):
    file = tmp_path / "sample.qasm"
    with open(file, "w") as io:
        qasm2_emit = emit.QASM2()
        qasm2_emit.emit(main)

    with open(file, "r") as io:
        generated = io.read()

    with open(Path(__file__).parent / "sample.qasm", "r") as io:
        target = io.read()

    assert generated.strip() == target.strip()

test_simple(Path("/tmp"))