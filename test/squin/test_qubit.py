from kirin import types

from bloqade import squin


def test_get_ids():
    @squin.kernel
    def main():
        q = squin.qubit.new(3)

        m = squin.qubit.measure(q)

        qid = squin.qubit.get_qubit_id(q[0])
        mid = squin.qubit.get_measurement_id(m[1])
        return mid + qid

    main.print()
    assert main.return_type.is_subseteq(types.Int)
