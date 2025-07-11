from bloqade.squin import qubit, kernel
from bloqade.analysis.measure_id import MeasurementIDAnalysis


# No control flow or loops,
# just simple single block program
def test_linear_measure_analysis():
    @kernel
    def main():
        n_qubits = 4
        q = qubit.new(n_qubits)
        meas_res = qubit.measure(q)

        # very contrived tuple just to make sure impl for tuple
        # propagates the right information through
        res = (meas_res[0], meas_res[1], meas_res[2])
        return res

    main.print()

    frame, _ = MeasurementIDAnalysis(kernel).run_analysis(main)
    main.print(analysis=frame.entries)


def test_scf_measure_analysis():
    @kernel
    def main():
        n_qubits = 4
        q = qubit.new(n_qubits)
        meas_res = qubit.measure(q)

        if meas_res[0]:
            if meas_res[1]:
                return 1
            else:
                return 2
        else:
            return 3

    main.print()

    frame, _ = MeasurementIDAnalysis(kernel).run_analysis(main)
    main.print(analysis=frame.entries)
