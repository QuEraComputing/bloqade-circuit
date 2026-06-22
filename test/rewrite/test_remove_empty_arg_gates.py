from typing import Any

from kirin import ir
from kirin.analysis import CallGraph
from kirin.dialects import py, func, ilist

from bloqade import qubit, squin
from bloqade.squin.gate import stmts as gate_stmts
from bloqade.squin.noise import stmts as noise_stmts
from bloqade.rewrite.passes import AggressiveUnroll, RemoveEmptyArgGates
from bloqade.rewrite.rules.remove_empty_arg_gates import _qubit_args, _get_ilist_len


def _invoke_names(mt) -> list[str]:
    return [
        stmt.callee.sym_name for stmt in mt.code.walk() if isinstance(stmt, func.Invoke)
    ]


def _walk_call_graph(mt):
    call_graph = CallGraph(mt)
    for method in set(call_graph.edges.keys()) | {mt}:
        yield from method.code.walk()


def test_removes_empty_stdlib_gate_and_noise_calls():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)
        squin.broadcast.x([])
        squin.broadcast.depolarize(0.1, [])

    RemoveEmptyArgGates(main.dialects)(main)

    stmts = list(_walk_call_graph(main))
    assert any(isinstance(stmt, gate_stmts.H) for stmt in stmts)
    assert not any(isinstance(stmt, gate_stmts.X) for stmt in stmts)
    assert not any(isinstance(stmt, noise_stmts.Depolarize) for stmt in stmts)


def test_preserves_nonempty_gate_and_noise_calls():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.x(q)
        squin.broadcast.depolarize(0.1, q)

    RemoveEmptyArgGates(main.dialects)(main)

    stmts = list(_walk_call_graph(main))
    assert any(isinstance(stmt, gate_stmts.X) for stmt in stmts)
    assert any(isinstance(stmt, noise_stmts.Depolarize) for stmt in stmts)


def test_removes_empty_measurement_and_preserves_empty_result():
    @squin.kernel
    def main():
        measurements = squin.qubit.broadcast.measure([])
        return len(measurements)

    RemoveEmptyArgGates(main.dialects)(main)

    assert main() == 0


def test_removes_nested_empty_qubit_lists():
    @squin.kernel
    def main():
        squin.broadcast.correlated_qubit_loss(0.1, [])

    RemoveEmptyArgGates(main.dialects)(main)

    assert not any(
        isinstance(stmt, noise_stmts.CorrelatedQubitLoss)
        for stmt in _walk_call_graph(main)
    )


def test_removes_two_qubit_gate_only_when_both_lists_are_empty():
    @squin.kernel
    def all_empty():
        squin.broadcast.cx([], [])

    @squin.kernel
    def partially_empty():
        q = squin.qalloc(1)
        squin.broadcast.cx([], q)

    RemoveEmptyArgGates(all_empty.dialects)(all_empty)
    RemoveEmptyArgGates(partially_empty.dialects)(partially_empty)

    assert not any(
        isinstance(stmt, gate_stmts.CX) for stmt in _walk_call_graph(all_empty)
    )
    assert any(
        isinstance(stmt, gate_stmts.CX) for stmt in _walk_call_graph(partially_empty)
    )


def test_preserves_nonquantum_function_called_with_empty_list():
    @squin.kernel
    def length(values: ilist.IList[int, Any]) -> int:
        return len(values)

    @squin.kernel
    def main():
        return length([])

    RemoveEmptyArgGates(main.dialects)(main)

    assert main() == 0


def test_preserves_user_function_containing_quantum_operation():
    @squin.kernel
    def custom_gate(qubits: ilist.IList[squin.qubit.Qubit, Any]):
        squin.broadcast.x(qubits)

    @squin.kernel
    def main():
        custom_gate([])

    RemoveEmptyArgGates(main.dialects)(main)

    assert "custom_gate" in _invoke_names(main)
    assert any(isinstance(stmt, gate_stmts.X) for stmt in _walk_call_graph(main))


def test_removes_direct_gate_after_inlining():
    @squin.kernel
    def main():
        squin.broadcast.x([])

    AggressiveUnroll(main.dialects).fixpoint(main)
    assert any(isinstance(stmt, gate_stmts.X) for stmt in main.code.walk())

    RemoveEmptyArgGates(main.dialects)(main)

    assert not any(isinstance(stmt, gate_stmts.X) for stmt in _walk_call_graph(main))


def test_removes_direct_measurement_after_inlining():
    @squin.kernel
    def main():
        return len(squin.qubit.broadcast.measure([]))

    AggressiveUnroll(main.dialects).fixpoint(main)
    RemoveEmptyArgGates(main.dialects)(main)

    assert main() == 0


def test_ignores_nonqubit_list_arguments():
    probabilities = [0.0] * 15

    @squin.kernel
    def main():
        squin.broadcast.two_qubit_pauli_channel(probabilities, [], [])

    RemoveEmptyArgGates(main.dialects)(main)

    assert not any(
        isinstance(stmt, noise_stmts.TwoQubitPauliChannel)
        for stmt in _walk_call_graph(main)
    )


def test_remove_direct_gate_on_empty_ilist():
    @squin.kernel
    def main():
        squin.qalloc(1)
        gate_stmts.X(qubits=ilist.IList([]))

    RemoveEmptyArgGates(main.dialects)(main)

    assert not any(isinstance(stmt, gate_stmts.Gate) for stmt in _walk_call_graph(main))


def test_remove_effectless_helper_function():
    @squin.kernel
    def only_empty_ops():
        squin.broadcast.x(ilist.IList([]))

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.broadcast.h(q)
        only_empty_ops()

    RemoveEmptyArgGates(main.dialects)(main)

    assert any(isinstance(stmt, gate_stmts.H) for stmt in _walk_call_graph(main))
    assert not any(isinstance(stmt, gate_stmts.X) for stmt in _walk_call_graph(main))


def test_removes_empty_rotation_gate():
    @squin.kernel
    def main():
        squin.broadcast.rx(0.5, [])

    RemoveEmptyArgGates(main.dialects)(main)

    assert not any(isinstance(stmt, gate_stmts.Rx) for stmt in _walk_call_graph(main))


def test_removes_empty_reset_without_using_result():
    @squin.kernel
    def main():
        squin.qubit.broadcast.reset([])

    RemoveEmptyArgGates(main.dialects)(main)

    assert not any(
        isinstance(stmt, qubit.stmts.Reset) for stmt in _walk_call_graph(main)
    )


def test_removes_unused_empty_measurement():
    @squin.kernel
    def main():
        squin.qubit.broadcast.measure([])

    RemoveEmptyArgGates(main.dialects)(main)

    assert not any(
        isinstance(stmt, qubit.stmts.Measure) for stmt in _walk_call_graph(main)
    )


def test_idempotent():
    @squin.kernel
    def main():
        squin.qalloc(2)
        squin.broadcast.x([])

    RemoveEmptyArgGates(main.dialects)(main)
    result2 = RemoveEmptyArgGates(main.dialects)(main)

    assert not result2.has_done_something
    assert not any(isinstance(stmt, gate_stmts.X) for stmt in _walk_call_graph(main))


def test_get_ilist_len_from_ilist_new_and_constants():
    empty_new = ilist.New(values=())
    empty_list = py.Constant([])
    empty_tuple = py.Constant(())
    ir.Block([empty_new, empty_list, empty_tuple])

    assert _get_ilist_len(empty_new.result) == 0
    assert _get_ilist_len(empty_list.result) == 0
    assert _get_ilist_len(empty_tuple.result) == 0


def test_qubit_args_returns_none_for_non_gate_statements():
    assert _qubit_args(py.Constant(0)) is None
