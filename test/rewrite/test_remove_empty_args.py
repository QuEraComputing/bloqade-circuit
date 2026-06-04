from typing import Any

from kirin.dialects import func, ilist

from bloqade import squin
from bloqade.squin import gate
from bloqade.rewrite.passes import AggressiveUnroll, RemoveEmptyArgGates


def test_removes_empty_stdlib_gate_and_noise_calls():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)
        squin.broadcast.x([])
        squin.broadcast.depolarize(0.1, [])

    RemoveEmptyArgGates(main.dialects)(main)

    invokes = [
        stmt.callee.sym_name
        for stmt in main.code.walk()
        if isinstance(stmt, func.Invoke)
    ]
    assert "h" in invokes
    assert "x" not in invokes
    assert "depolarize" not in invokes


def test_preserves_nonempty_gate_and_noise_calls():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.x(q)
        squin.broadcast.depolarize(0.1, q)

    RemoveEmptyArgGates(main.dialects)(main)

    invokes = [
        stmt.callee.sym_name
        for stmt in main.code.walk()
        if isinstance(stmt, func.Invoke)
    ]
    assert "x" in invokes
    assert "depolarize" in invokes


def test_removes_empty_measurement_and_preserves_empty_result():
    @squin.kernel
    def main():
        measurements = squin.qubit.broadcast.measure([])
        return len(measurements)

    RemoveEmptyArgGates(main.dialects)(main)

    assert main() == 0
    assert not any(
        isinstance(stmt, func.Invoke) and stmt.callee.sym_name == "measure"
        for stmt in main.code.walk()
    )


def test_removes_nested_empty_qubit_lists():
    @squin.kernel
    def main():
        squin.broadcast.correlated_qubit_loss(0.1, [])

    RemoveEmptyArgGates(main.dialects)(main)

    assert not any(
        isinstance(stmt, func.Invoke)
        and stmt.callee.sym_name == "correlated_qubit_loss"
        for stmt in main.code.walk()
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
        isinstance(stmt, func.Invoke) and stmt.callee.sym_name == "cx"
        for stmt in all_empty.code.walk()
    )
    assert any(
        isinstance(stmt, func.Invoke) and stmt.callee.sym_name == "cx"
        for stmt in partially_empty.code.walk()
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

    assert any(
        isinstance(stmt, func.Invoke) and stmt.callee.sym_name == "custom_gate"
        for stmt in main.code.walk()
    )


def test_removes_direct_gate_after_inlining():
    @squin.kernel
    def main():
        squin.broadcast.x([])

    AggressiveUnroll(main.dialects).fixpoint(main)
    assert any(isinstance(stmt, gate.stmts.X) for stmt in main.code.walk())

    RemoveEmptyArgGates(main.dialects)(main)

    assert not any(isinstance(stmt, gate.stmts.X) for stmt in main.code.walk())


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
        isinstance(stmt, func.Invoke)
        and stmt.callee.sym_name == "two_qubit_pauli_channel"
        for stmt in main.code.walk()
    )
