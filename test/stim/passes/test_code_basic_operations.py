"""
The tests here are part of a "base structure"
that comes up in standard QEC operations, chiefly
- Extracting qubits to be ancilla and data qubits
- Applying entangling rounds/operations on the
physical qubits
- Extracting measurements and setting detectors

They previously helped debug some problems with the
PhysicalAndSquinToStim pass and are included here
"""

import os
from typing import Any

from kirin import ir
from kirin.dialects import ilist

from bloqade import squin
from bloqade.types import Qubit
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass


def load_stim_reference(filename):
    path = os.path.join(
        os.path.dirname(__file__), "stim_reference_programs", "annotate", filename
    )
    with open(path, "r") as f:
        return f.read()


def codegen(mt: ir.Method):
    # method should not have any arguments!
    emit = EmitStimMain()
    emit.initialize()
    emit.run(mt=mt, args=())
    return emit.get_output()


def test_no_kernel_base_op():

    qids = [0, 2, 1]

    @squin.kernel
    def test():
        total_q = squin.qalloc(4)

        def get_qubit(idx: int) -> Qubit:
            return total_q[idx]

        # create a subset of qubits
        ## use ilist.map to work around
        sub_q = ilist.map(get_qubit, qids)

        squin.broadcast.x(sub_q)
        m = squin.broadcast.measure(sub_q)

        for i in range(len(m)):
            squin.annotate.set_detector(measurements=[m[i]], coordinates=(0, 0))

    SquinToStimPass(dialects=test.dialects)(test)

    base_stim_prog = load_stim_reference("no_kernel_base_op.stim")

    assert base_stim_prog == codegen(test)


def test_kernel_base_op():

    a_idxs = [1, 3, 2]

    @squin.kernel
    def get_a_qubits(q: ilist.IList[Qubit, Any]):
        def get_qubit(idx: int) -> Qubit:
            return q[idx]

        return ilist.map(get_qubit, a_idxs)

    @squin.kernel
    def measure_out(q: ilist.IList[Qubit, Any]):
        aq = get_a_qubits(q)

        squin.broadcast.h(aq)
        m_a = squin.broadcast.measure(aq)
        return m_a

    @squin.kernel
    def main():
        qubits = squin.qalloc(6)
        mr = measure_out(qubits)

        for i in range(len(mr)):
            squin.set_detector(measurements=[mr[i]], coordinates=(0, 0))

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_stim_reference("kernel_base_op.stim")

    assert base_stim_prog == codegen(main)
