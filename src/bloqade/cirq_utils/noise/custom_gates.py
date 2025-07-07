import cirq
import numpy as np


class TwoQubitPauli(cirq.Gate):
    """
    A custom two-qubit gate that applies a user-defined Pauli error channel.

    This gate represents a noisy two-qubit operation described as a probabilistic mixture
    over the 16 possible tensor products of single-qubit Pauli operators.

    The input is a 4x4 matrix `p` where `p[i, j]` defines the probability of applying the
    two-qubit Pauli operator formed by the Kronecker product of the `i`-th and `j`-th Pauli operators.
    The index order is assumed to be: 0=I, 1=X, 2=Y, 3=Z.

    Attributes:
        _p (np.ndarray): A 4x4 array of Pauli pair probabilities.

    Methods:
        _mixture_: Returns the probabilistic mixture of unitary operators representing the noisy channel.
        _num_qubits_: Specifies that the gate acts on 2 qubits.
        _has_mixture_: Declares that the gate is a mixed quantum channel.
        _circuit_diagram_info_: Provides labels for circuit visualization.

    Example:
        >>> probs = np.zeros((4, 4))
        >>> probs[1, 1] = 0.1  # X⊗X error
        >>> gate = TwoQubitPauli(probs)
        >>> circuit = cirq.Circuit(gate.on(cirq.LineQubit(0), cirq.LineQubit(1)))
    """

    def __init__(self, p: np.ndarray) -> None:
        if p.shape != (4, 4):
            raise ValueError("Expected a 4x4 array of probabilities")
        self._p = p

    def _num_qubits_(self) -> int:
        return 2

    def _has_mixture_(self) -> bool:
        return True

    def _mixture_(self):
        # Identity: no error
        ps = []
        ops = []

        # Pauli matrices
        paulis = [cirq.I, cirq.X, cirq.Y, cirq.Z]

        # Construct all 2-qubit Pauli error ops
        for i, p1 in enumerate(paulis):
            for j, p2 in enumerate(paulis):
                p = self._p[i, j]
                if p > 0:
                    op = np.kron(cirq.unitary(p1), cirq.unitary(p2))
                    ps.append(p)
                    ops.append(op)

        return tuple(zip(ps, ops))

    def _circuit_diagram_info_(self, args) -> cirq.CircuitDiagramInfo:
        return cirq.CircuitDiagramInfo(wire_symbols=("TQP", "TQP"), connected=True)
