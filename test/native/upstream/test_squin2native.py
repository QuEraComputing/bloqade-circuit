import numpy as np
import pytest
from kirin.analysis import callgraph

from bloqade import squin
from bloqade.squin import gate
from bloqade.pyqrack import StackMemorySimulator
from bloqade.native.dialects import gate as native_gate
from bloqade.native.upstream import GateRule, SquinToNative


@pytest.mark.parametrize("stmt_type", gate.dialect.stmts)
def test_stmt_map(stmt_type: type):
    assert (
        stmt_type in GateRule.SQUIN_MAPPING
    ), f"{stmt_type} not in GateRule.SQUIN_MAPPING"


def test_ghz():

    n = 8

    @squin.kernel
    def main():
        q = squin.qalloc(n)
        squin.h(q[0])

        for i in range(n - 1):
            squin.cx(q[i], q[i + 1])

        squin.broadcast.sqrt_x_adj(q)

    new_main = SquinToNative().emit(main, no_raise=True)

    new_callgraph = callgraph.CallGraph(new_main)
    # make sure all kernels have been converted to native gate
    all_kernels = (ker for kers in new_callgraph.defs.values() for ker in kers)
    for ker in all_kernels:
        assert gate.dialect not in ker.dialects
        assert native_gate.dialect in ker.dialects

    # test to make sure the statevectors are the same
    # before and after conversion to native gate
    old_sv = np.asarray(StackMemorySimulator(min_qubits=n).state_vector(main))
    old_sv /= old_sv[imax := np.abs(old_sv).argmax()] / np.abs(old_sv[imax])

    new_sv = np.asarray(StackMemorySimulator(min_qubits=n).state_vector(new_main))
    new_sv /= new_sv[imax := np.abs(new_sv).argmax()] / np.abs(new_sv[imax])

    assert np.allclose(old_sv, new_sv)
