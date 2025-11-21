# from kirin.passes.fold import Fold

from bloqade import squin

# from bloqade.stim.passes import SquinToStimPass
from bloqade.analysis.record import RecordAnalysis

# from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.stim.passes.soft_flatten import SoftFlatten

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
frame, _ = RecordAnalysis(dialects=test.dialects).run(test)
test.print(analysis=frame.entries)
"""

"""
def hint_const_failure():

    @squin.kernel
    def test():
        qs = squin.qalloc(3)
        ms0 = squin.broadcast.measure(qs)
        i = 0
        for _ in range(5):
            ms1 = squin.broadcast.measure(qs)
            squin.set_detector([ms0[i], ms1[i]], coordinates=[i, i])

    # SoftFlatten(dialects=test.dialects).fixpoint(test)
    Fold(dialects=test.dialects, no_raise=False).fixpoint(test)
    test.print(hint="const")
    # frame, _ = RecordAnalysis(dialects=test.dialects).run(test)
    # test.print(analysis=frame.entries, hint="const")


# Problematic having the variable substitution happen at the end
"""


def test_custom_const_carrier():

    @squin.kernel(fold=False)
    def test(x: int):
        y = None
        z = None
        for _ in range(5):
            f = [1, 2, 3, 4, 5, 5, 6, 7, 8]
            z = slice(0, 2)
            y = f[z]
            y[0] += x
        return y, z

    SoftFlatten(dialects=test.dialects).fixpoint(test)
    test.print()
    frame, _ = RecordAnalysis(dialects=test.dialects).run(test)
    test.print(analysis=frame.entries, hint="const")


"""
def assignment_last_rep_code():
    @squin.kernel(fold=True)
    def test():

        qs = squin.qalloc(5)
        data_qs = [qs[0], qs[2], qs[4]]
        and_qs = [qs[1], qs[3]]

        init_and_ms = squin.broadcast.measure(and_qs)

        squin.set_detector([init_and_ms[0]], coordinates=[0, 0])
        squin.set_detector([init_and_ms[1]], coordinates=[0, 1])

        # loop_and_ms = None
        for _ in range(5):
            loop_and_ms = squin.broadcast.measure(and_qs)
            squin.annotate.set_detector([loop_and_ms[0], init_and_ms[0]], coordinates=[0,0])
            squin.annotate.set_detector([loop_and_ms[1], init_and_ms[1]], coordinates=[1,1])

            #for i in range(len(curr_ms)):
            #    squin.annotate.set_detector([curr_ms[i], prev_ms[i]], coordinates=[1,1])

            ##init_and_ms = loop_and_ms

        #data_ms = squin.broadcast.measure(data_qs)
        #squin.set_detector(
        #    [data_ms[0], data_ms[1], loop_and_ms[0]], coordinates=[2, 0]
        #)
        #squin.set_detector(
        #    [data_ms[2], data_ms[1], loop_and_ms[1]], coordinates=[2, 1]
        #)


    SoftFlatten(dialects=test.dialects).fixpoint(test)
    test.print()
    frame, _ = RecordAnalysis(dialects=test.dialects).run(test)
    test.print(analysis=frame.entries, hint="const")

"""

"""
from kirin.prelude import structural_no_opt

@structural_no_opt
def demo():

    a = 0
    b= 1
    for _ in range(10):
        c = b
        b = a
        a = c

demo.print()
"""


def assignment_first_rep_code():
    @squin.kernel
    def test():

        qs = squin.qalloc(5)
        data_qs = [qs[0], qs[2], qs[4]]
        and_qs = [qs[1], qs[3]]

        curr_ms = squin.broadcast.measure(and_qs)  # 2 meas
        squin.set_detector([curr_ms[0]], coordinates=[0, 0])
        squin.set_detector([curr_ms[1]], coordinates=[0, 1])

        for _ in range(5):
            # prev lives entirely in the loop
            prev_ms = curr_ms
            curr_ms = squin.broadcast.measure(and_qs)  # another 2 meas
            squin.annotate.set_detector([prev_ms[0], curr_ms[0]], coordinates=[0, 0])
            squin.annotate.set_detector([prev_ms[1], curr_ms[1]], coordinates=[0, 1])

        data_ms = squin.broadcast.measure(data_qs)  # 3 meas

        squin.set_detector([data_ms[0], data_ms[1], curr_ms[0]], coordinates=[2, 0])
        squin.set_detector([data_ms[2], data_ms[1], curr_ms[1]], coordinates=[2, 1])
        squin.set_observable([data_ms[2]])

    SoftFlatten(dialects=test.dialects).fixpoint(test)
    test.print()
    frame, _ = RecordAnalysis(dialects=test.dialects).run(test)
    test.print(analysis=frame.entries)

    # frame, _ = MeasurementIDAnalysis(dialects=test.dialects).run(test)
    # test.print(analysis=frame.entries)


assignment_first_rep_code()

"""
@squin.kernel
def analysis_demo():
    qs = squin.qalloc(3)
    ms0 = squin.broadcast.measure(qs)
    ms1 = squin.broadcast.measure(qs)
    squin.set_detector(ms0, coordinates=[0, 0]) # -4 -5 -6
    squin.set_detector(ms1, coordinates=[0, 1]) # -1 -2 -3
    # squin.broadcast.measure(qs)
    squin.set_detector(ms1, coordinates=[0, 2]) # -4 -5 -6

    # get aliasing to work
    ms1 = ms0
    squin.set_detector(ms1, coordinates=[1, 0]) # should also be -4 -5 -6


SoftFlatten(dialects=analysis_demo.dialects).fixpoint(analysis_demo)
analysis_demo.print()
frame, _ = RecordAnalysis(dialects=analysis_demo.dialects).run(analysis_demo)
analysis_demo.print(analysis=frame.entries)
"""
