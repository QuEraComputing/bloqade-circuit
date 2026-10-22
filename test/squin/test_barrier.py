import io

import numpy as np
import pytest
from kirin import ir, passes, rewrite
from kirin.dialects import ilist

from bloqade import qubit, squin
from bloqade.types import Qubit
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.native.upstream import SquinToNative


def test_barriers_survive_folding_inlining_and_dce():
    @squin.kernel
    def boundary(q: Qubit):
        squin.barrier(q)

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        for _ in range(2):
            boundary(q[0])
        squin.broadcast.barrier(q)

    AggressiveUnroll(main.dialects, no_raise=False).fixpoint(main)
    passes.Fold(main.dialects, no_raise=False).fixpoint(main)
    rewrite.Walk(
        rewrite.Chain(
            rewrite.DeadCodeElimination(), rewrite.CommonSubexpressionElimination()
        )
    ).rewrite(main.code)
    main.verify()
    main.verify_type()

    barriers = [s for s in main.code.walk() if isinstance(s, qubit.stmts.Barrier)]
    assert len(barriers) == 3
    registers = [s.qubits.owner for s in barriers]
    assert all(isinstance(register, ilist.New) for register in registers)
    assert [
        len(register.values)
        for register in registers
        if isinstance(register, ilist.New)
    ] == [1, 1, 2]
    assert not any(s.has_trait(ir.Pure) for s in barriers)


@pytest.mark.parametrize("to_native", [False, True])
def test_barrier_preserves_simulated_state(to_native):
    from bloqade.pyqrack import StackMemorySimulator

    @squin.kernel
    def reference():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        squin.rz(0.37, q[0])
        squin.rx(0.12, q[0])

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.broadcast.barrier(q)
        squin.cx(q[0], q[1])
        squin.rz(0.37, q[0])
        squin.barrier(q[0])
        squin.rx(0.12, q[0])

    if to_native:
        main = SquinToNative().emit(main, no_raise=False)
        AggressiveUnroll(main.dialects, no_raise=False).fixpoint(main)
        assert sum(isinstance(s, qubit.stmts.Barrier) for s in main.code.walk()) == 2
    sim = StackMemorySimulator(min_qubits=2)
    assert np.abs(
        np.vdot(sim.state_vector(main), sim.state_vector(reference))
    ) == pytest.approx(1.0, abs=1e-6)


def test_barrier_stim_export():
    from bloqade import stim
    from bloqade.stim.emit import EmitStimMain
    from bloqade.stim.passes import SquinToStimPass

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.x(q[0])
        squin.barrier(q[0])
        squin.x(q[0])
        squin.broadcast.barrier(q)
        squin.broadcast.measure(q)

    SquinToStimPass(main.dialects, no_raise=False)(main)
    buf = io.StringIO()
    emit = EmitStimMain(dialects=stim.main, io=buf)
    emit.initialize()
    emit.run(main)
    assert buf.getvalue().strip().splitlines() == [
        "X 0",
        "TICK",
        "X 0",
        "TICK",
        "MZ(0.00000000) 0 1",
    ]


def test_barrier_cirq_export():
    import cirq

    from bloqade.cirq_utils import emit_circuit

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.broadcast.barrier(q)
        squin.cx(q[0], q[1])

    actual = emit_circuit(main)
    q0, q1 = cirq.LineQubit.range(2)
    expected = cirq.Circuit(cirq.H(q0), cirq.CNOT(q0, q1))
    assert actual == expected
