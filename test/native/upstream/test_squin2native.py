import numpy as np
from kirin.analysis import callgraph

from bloqade import squin
from bloqade.squin import clifford
from bloqade.pyqrack import StackMemorySimulator
from bloqade.native.dialects import gates
from bloqade.native.upstream import SquinToNative


def integration_test():

    n = 8

    @squin.kernel
    def main():
        q = squin.qubit.new(n)
        squin.h(q[0])

        for i in range(n - 1):
            squin.cx(q[i], q[i + 1])

    new_main = SquinToNative().emit(main)

    new_callgraph = callgraph.CallGraph(new_main)

    all_kernels = (ker for kers in new_callgraph.defs.values() for ker in kers)
    for ker in all_kernels:
        assert clifford.dialect not in ker.dialects
        assert gates.dialect in ker.dialects

    old_sv = np.asarray(StackMemorySimulator().state_vector(main))
    new_sv = np.asarray(StackMemorySimulator().state_vector(new_main))

    old_sv /= old_sv[imax := np.abs(old_sv).argmax()] / np.abs(old_sv[imax])
    new_sv /= new_sv[imax := np.abs(new_sv).argmax()] / np.abs(new_sv[imax])

    assert np.allclose(old_sv, new_sv)
