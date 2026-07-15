from bloqade import squin
from bloqade.analysis.measure_id import MeasurementIDAnalysis
from bloqade.stim.passes.flatten import Flatten


@squin.kernel
def test():
    qs = squin.qalloc(5)
    ms = squin.broadcast.measure(qs)
    squin.set_detector([ms[0]], coordinates=[0, 0])
    new_ms = squin.broadcast.measure(qs)
    squin.set_detector([new_ms[0]], coordinates=[0, 0])

    return ms


Flatten(test.dialects).fixpoint(test)
frame, _ = MeasurementIDAnalysis(test.dialects).run(test)

test.print(analysis=frame.entries)
