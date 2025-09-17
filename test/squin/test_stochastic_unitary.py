from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator


def test_stochastic_unitary():
    @squin.kernel
    def main():
        x = squin.op.x()
        y = squin.op.y()
        ps = [0.1, 0.2]
        su = squin.noise.stochastic_unitary_channel([x, y], ps)
        q = squin.qubit.new(2)
        squin.qubit.broadcast(su, q)

    main.print()

    sim = StackMemorySimulator(min_qubits=2)
    sim.run(main)
