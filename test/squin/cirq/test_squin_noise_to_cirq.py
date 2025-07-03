import cirq

from bloqade import squin


def test_pauli_channel(run_sim: bool = False):
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        h = squin.op.h()
        cx = squin.op.cx()
        squin.qubit.apply(h, q[0])
        dpl = squin.noise.depolarize(0.1)
        squin.qubit.apply(dpl, q[0])
        squin.qubit.apply(cx, q)
        single_qubit_noise = squin.noise.single_qubit_pauli_channel([0.1, 0.12, 0.13])
        squin.qubit.apply(single_qubit_noise, q[1])
        two_qubit_noise = squin.noise.two_qubit_pauli_channel(
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
            ]
        )
        squin.qubit.apply(two_qubit_noise, q)
        squin.qubit.measure(q)

    main.print()

    circuit = squin.cirq.emit_circuit(main)

    print(circuit)

    if run_sim:
        sim = cirq.Simulator()
        sim.run(circuit)


def test_pauli_error(run_sim: bool = False):
    @squin.kernel
    def main():
        q = squin.qubit.new(2)
        x = squin.op.x()
        n = squin.noise.pauli_error(x, 0.1)
        squin.qubit.apply(n, q[0])
        squin.qubit.measure(q)

    main.print()

    circuit = squin.cirq.emit_circuit(main)

    print(circuit)

    if run_sim:
        sim = cirq.Simulator()
        sim.run(circuit)


def test_pperror(run_sim: bool = False):
    @squin.kernel
    def main():
        q = squin.qubit.new(3)
        ps = squin.op.pauli_string(string="XYZ")
        n = squin.noise.pp_error(ps, 0.1)
        squin.qubit.apply(n, q)
        squin.qubit.measure(q)

    main.print()

    circuit = squin.cirq.emit_circuit(main)

    print(circuit)

    if run_sim:
        sim = cirq.Simulator()
        sim.run(circuit)
