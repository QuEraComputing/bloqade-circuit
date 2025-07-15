from bloqade import squin
from bloqade.squin import qubit
from bloqade.squin.qubit import MeasurementResult
from bloqade.stim.upstream import squin_to_stim


def test_accessing_from_list():

    @squin.kernel(fold=False)
    def main():
        q = qubit.new(2)
        results = []

        result: MeasurementResult = qubit.measure(q[0])
        results += [result]
        result: MeasurementResult = qubit.measure(q[1])
        results += [result]

    main.print()

    new_ker = squin_to_stim(mt=main)
    new_ker.print()
