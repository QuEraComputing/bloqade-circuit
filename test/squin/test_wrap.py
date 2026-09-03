import pytest

from bloqade import squin
from bloqade.types import Qubit
from bloqade.pyqrack import StackMemorySimulator


def test_wrap_infers_qubit_count_and_measures():
    @squin.kernel
    def bell(q0: Qubit, q1: Qubit):
        squin.h(q0)
        squin.cx(q0, q1)

    main = squin.wrap(bell)

    main.print()
    sim = StackMemorySimulator(min_qubits=2)
    result = sim.run(main)

    assert len(result) == 2


def test_wrap_binds_keyword_arguments():
    @squin.kernel
    def rotate(q: Qubit, theta: float):
        squin.rx(theta, q)

    main = squin.wrap(rotate, theta=0.125)

    main.print()
    sim = StackMemorySimulator(min_qubits=1)
    result = sim.run(main)

    assert len(result) == 1


def test_wrap_accepts_explicit_qubit_count_with_keywords():
    @squin.kernel
    def ansatz(q0: Qubit, q1: Qubit, theta: float):
        squin.rx(theta, q0)
        squin.cx(q0, q1)

    main = squin.wrap(ansatz, 2, theta=0.125)

    main.print()
    sim = StackMemorySimulator(min_qubits=2)
    result = sim.run(main)

    assert len(result) == 2


def test_wrap_rejects_mismatched_argument_count():
    @squin.kernel
    def two_qubit(q0: Qubit, q1: Qubit):
        squin.cx(q0, q1)

    with pytest.raises(ValueError, match="expected 2 total arguments"):
        squin.wrap(two_qubit, 1)


def test_wrap_rejects_unexpected_keyword_argument():
    @squin.kernel
    def one_qubit(q: Qubit):
        squin.h(q)

    with pytest.raises(TypeError, match="unexpected keyword argument"):
        squin.wrap(one_qubit, theta=0.125)


def test_wrap_rejects_qubit_bound_by_keyword():
    @squin.kernel
    def ansatz(q0: Qubit, q1: Qubit, theta: float):
        squin.rx(theta, q0)
        squin.cx(q0, q1)

    with pytest.raises(TypeError, match="cannot be bound by keyword: q0"):
        squin.wrap(ansatz, 2, q0=object(), theta=0.125)
