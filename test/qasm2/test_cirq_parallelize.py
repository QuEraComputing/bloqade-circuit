import cirq
from bloqade.qasm2.rewrite.cirq_parallelize import parallelizer


def test1():
    qubits = cirq.LineQubit.range(8)
    circuit = cirq.Circuit(
        cirq.H(qubits[0]),
        cirq.CX(qubits[0], qubits[1]),
        cirq.CX(qubits[0], qubits[2]),
        cirq.CX(qubits[1], qubits[3]),
        cirq.CX(qubits[0], qubits[4]),
        cirq.CX(qubits[1], qubits[5]),
        cirq.CX(qubits[2], qubits[6]),
        cirq.CX(qubits[3], qubits[7]),
    )

    circuit2 = parallelizer(circuit)
    print(circuit2)
    assert len(circuit2.moments) == 7


if __name__ == "__main__":
    test1()
