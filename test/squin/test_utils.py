from typing import Any

import pytest
from kirin.dialects import ilist

from bloqade import squin
from bloqade.types import Qubit
from bloqade.pyqrack import StackMemorySimulator


def test_wrap_explicit_qubits_with_keyword_constant():
    @squin.kernel
    def kernel(q0: Qubit, q1: Qubit, theta: float) -> None:
        squin.rx(theta, q0)
        squin.cx(q0, q1)

    wrapped = squin.wrap(kernel, theta=0.25)

    wrapped.print()
    wrapped.verify()
    wrapped.verify_type()

    assert wrapped.arg_names == ["#self#"]
    StackMemorySimulator(min_qubits=2).run(wrapped)


def test_wrap_explicit_qubits_with_positional_constant():
    @squin.kernel
    def kernel(theta: float, q0: Qubit) -> None:
        squin.rx(theta, q0)

    wrapped = squin.wrap(kernel, 0.25)

    wrapped.print()
    StackMemorySimulator(min_qubits=1).run(wrapped)


def test_wrap_rejects_qubit_register_argument():
    @squin.kernel
    def kernel(qs: ilist.IList[Qubit, Any]) -> None:
        squin.broadcast.x(qs)

    with pytest.raises(ValueError, match="individual Qubit arguments"):
        squin.wrap(kernel)


def test_wrap_requires_constant_arguments():
    @squin.kernel
    def kernel(q0: Qubit, theta: float) -> None:
        squin.rx(theta, q0)

    with pytest.raises(ValueError, match="Missing constant value"):
        squin.wrap(kernel)
