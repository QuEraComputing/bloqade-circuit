from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator


def test_annotate_statements_are_ignored():
    """A kernel containing `annotate` statements runs on PyQrack.

    `set_detector` / `set_observable` are decoder annotations with no effect on
    state-vector simulation. They used to raise `Missing implementation`; now
    they are skipped as no-ops so the kernel executes (see issue #628).
    """

    @squin.kernel
    def with_annotations():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        ms = squin.broadcast.measure(q)
        squin.set_detector([ms[0], ms[1]], coordinates=(0.0, 0.0))
        squin.set_observable([ms[0]])
        return q

    sim = StackMemorySimulator(min_qubits=2)
    qubits = sim.run(with_annotations)

    assert len(qubits) == 2
