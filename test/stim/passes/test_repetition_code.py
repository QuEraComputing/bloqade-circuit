from bloqade import squin
from bloqade.stim.passes import SquinToStimPass


def test_repeat_on_gates_only():

    @squin.kernel
    def test():

        qs = squin.qalloc(3)

        squin.broadcast.reset(qs)

        for _ in range(5):
            squin.broadcast.h(qs)
            squin.broadcast.x(qs)

    SquinToStimPass(dialects=test.dialects)(test)
    test.print()


def test_repeat_with_invariant_measure():

    @squin.kernel
    def test():

        qs = squin.qalloc(3)
        curr_ms = squin.broadcast.measure(qs)

        for _ in range(5):
            prev_ms = curr_ms
            squin.broadcast.h(qs)
            curr_ms = squin.broadcast.measure(qs)
            squin.set_detector(
                measurements=[curr_ms[0], prev_ms[0]], coordinates=[0, 0]
            )

    SquinToStimPass(dialects=test.dialects)(test)
    test.print()


test_repeat_with_invariant_measure()


def test_rep_code():
    @squin.kernel
    def test():

        qs = squin.qalloc(5)
        data_qs = [qs[0], qs[2], qs[4]]
        and_qs = [qs[1], qs[3]]

        squin.broadcast.reset(qs)
        squin.broadcast.cx(controls=[qs[0], qs[2]], targets=[qs[1], qs[3]])
        squin.broadcast.cx(controls=[qs[2], qs[4]], targets=[qs[1], qs[3]])

        curr_ms = squin.broadcast.measure(and_qs)
        squin.set_detector([curr_ms[0]], coordinates=[0, 0])
        squin.set_detector([curr_ms[1]], coordinates=[0, 1])

        for _ in range(3):

            prev_ms = curr_ms

            squin.broadcast.cx(controls=[qs[0], qs[2]], targets=[qs[1], qs[3]])
            squin.broadcast.cx(controls=[qs[2], qs[4]], targets=[qs[1], qs[3]])

            curr_ms = squin.broadcast.measure(and_qs)

            squin.annotate.set_detector([prev_ms[0], curr_ms[0]], coordinates=[0, 0])
            squin.annotate.set_detector([prev_ms[1], curr_ms[1]], coordinates=[0, 1])

        data_ms = squin.broadcast.measure(data_qs)

        squin.set_detector([data_ms[0], data_ms[1], curr_ms[0]], coordinates=[2, 0])
        squin.set_detector([data_ms[2], data_ms[1], curr_ms[1]], coordinates=[2, 1])
        squin.set_observable([data_ms[2]])

    SquinToStimPass(dialects=test.dialects)(test)
    test.print()
