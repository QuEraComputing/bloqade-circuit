from bloqade import squin

# from bloqade.analysis.record import RecordAnalysis
# from bloqade.stim.passes.soft_flatten import SoftFlatten

"""

@squin.kernel
def test():
    qs = squin.qalloc(5)
    data_qs = [qs[0], qs[2], qs[4]]
    and_qs = [qs[1], qs[3]]

    init_and_meas_res = squin.broadcast.measure(and_qs)
    squin.set_detector([init_and_meas_res[0]], coordinates=[0, 0])
    squin.set_detector([init_and_meas_res[1]], coordinates=[0, 1])

    and_meas_res = None
    for _ in range(10):
        and_meas_res = squin.broadcast.measure(and_qs)

        squin.set_detector([and_meas_res[0], init_and_meas_res[0]], coordinates=[0, 0])
        squin.set_detector([and_meas_res[1], init_and_meas_res[1]], coordinates=[1, 1])

        init_and_meas_res = and_meas_res

    data_meas_res = squin.broadcast.measure(data_qs)
    squin.set_detector(
        [data_meas_res[0], data_meas_res[1], and_meas_res[0]], coordinates=[2, 0]
    )
    squin.set_detector(
        [data_meas_res[2], data_meas_res[1], and_meas_res[1]], coordinates=[2, 1]
    )
    squin.set_observable([data_meas_res[0]])

    # return and_meas_res


test.print()
SoftFlatten(dialects=test.dialects).fixpoint(test)
test.print()
frame, _ = RecordAnalysis(dialects=test.dialects).run_analysis(test)
test.print(analysis=frame.entries)
"""


@squin.kernel
def analysis_demo():
    qs = squin.qalloc(3)
    ms0 = squin.broadcast.measure(qs)
    ms1 = squin.broadcast.measure(qs)
    squin.set_detector(ms0, coordinates=(0, 0))
    squin.set_detector(ms1, coordinates=(0, 1))
    squin.broadcast.measure(qs)
    squin.set_detector(ms1, coordinates=(0, 2))

    # get aliasing to work
    ms1 = ms0
    squin.set_detector(ms1, coordinates=(1, 0))
    # return ms1


# SoftFlatten(dialects=analysis_demo.dialects).fixpoint(analysis_demo)
# analysis_demo.print()
# frame, _ = RecordAnalysis(dialects=analysis_demo.dialects).run_analysis(analysis_demo)
# analysis_demo.print(analysis=frame.entries)
