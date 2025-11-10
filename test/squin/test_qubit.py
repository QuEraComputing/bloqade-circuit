from kirin import types

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator
from bloqade.pyqrack.reg import Measurement


def test_get_ids():
    @squin.kernel
    def main():
        q = squin.qalloc(3)

        m = squin.broadcast.measure(q)

        qid = squin.qubit.get_qubit_id(q[0])
        mid = squin.qubit.get_measurement_id(m[1])
        return mid + qid

    main.print()
    assert main.return_type.is_subseteq(types.Int)

    @squin.kernel(fold=False)
    def main2():
        q = squin.qalloc(2)

        qid = squin.qubit.get_qubit_id(q[0])
        m1 = squin.qubit.measure(q[qid])

        squin.x(q[qid])
        m2 = squin.qubit.measure(q[qid])

        m1_id = squin.qubit.get_measurement_id(m1)
        m2_id = squin.qubit.get_measurement_id(m2)

        if m1_id != 0:
            # do something that errors
            q[0] + 1

        if m2_id != 1:
            q[0] + 1

        return squin.broadcast.measure(q)

    sim = StackMemorySimulator(min_qubits=2)
    result = sim.run(main2)
    for i, res in enumerate(result):
        assert isinstance(res, Measurement)
        assert res.measurement_id == i + 2
