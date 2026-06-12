from kirin import ir
from kirin.analysis import CallGraph
from kirin.dialects import func

from bloqade import qubit, squin
from bloqade.squin import gate, noise
from bloqade.rewrite.passes import RemoveEmptyArgGates


def _all_stmts(mt: ir.Method):
    methods = set(CallGraph(mt).edges.keys())
    methods.add(mt)
    for method in methods:
        for block in method.code.body.blocks:
            yield from block.stmts


def _count(mt: ir.Method, stmt_type: type[ir.Statement]) -> int:
    return sum(isinstance(stmt, stmt_type) for stmt in _all_stmts(mt))


def test_removes_empty_broadcast_gate_from_callgraph():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)
        squin.broadcast.x([])

    RemoveEmptyArgGates(main.dialects)(main)

    assert _count(main, gate.stmts.H) == 1
    assert _count(main, gate.stmts.X) == 0


def test_removes_empty_noise_measure_and_reset():
    @squin.kernel
    def main():
        squin.broadcast.depolarize(0.1, [])
        squin.broadcast.reset([])
        return squin.broadcast.measure([])

    RemoveEmptyArgGates(main.dialects)(main)

    assert _count(main, noise.stmts.Depolarize) == 0
    assert _count(main, qubit.stmts.Reset) == 0
    assert _count(main, qubit.stmts.Measure) == 0


def test_deletes_calls_to_kernels_that_become_empty():
    @squin.kernel
    def only_empty():
        squin.broadcast.x([])

    @squin.kernel
    def main():
        only_empty()

    RemoveEmptyArgGates(main.dialects)(main)

    assert _count(main, gate.stmts.X) == 0
    assert _count(main, func.Invoke) == 0
