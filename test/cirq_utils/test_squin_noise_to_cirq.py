import cirq

from bloqade import squin
from bloqade.cirq_utils import emit_circuit


def test_pauli_channel(run_sim: bool = False):
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.depolarize(0.1, q[0])
        squin.cx(q[0], q[1])
        squin.single_qubit_pauli_channel(0.1, 0.12, 0.13, q[1])
        squin.two_qubit_pauli_channel(
            [
                0.036,
                0.007,
                0.035,
                0.022,
                0.063,
                0.024,
                0.006,
                0.033,
                0.014,
                0.019,
                0.023,
                0.058,
                0.0,
                0.0,
                0.064,
            ],
            q[0],
            q[1],
        )
        squin.broadcast.measure(q)

    main.print()

    circuit = emit_circuit(main)

    print(circuit)

    if run_sim:
        sim = cirq.Simulator()
        sim.run(circuit)
