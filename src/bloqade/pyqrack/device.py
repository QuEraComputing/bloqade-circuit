from typing import Any, Union, TypeVar, ParamSpec, TypeAlias, NamedTuple
from numbers import Real, Integral
from collections import Counter
from dataclasses import field, dataclass
from collections.abc import Mapping, Hashable, Iterable, Sequence

import numpy as np
from kirin import ir
from kirin.dialects.ilist import IList

from pyqrack.pauli import Pauli
from bloqade.device import AbstractSimulatorDevice
from bloqade.pyqrack.reg import PyQrackQubit, MeasurementResultValue
from bloqade.pyqrack.base import (
    MemoryABC,
    StackMemory,
    DynamicMemory,
    PyQrackOptions,
    PyQrackInterpreter,
    _default_pyqrack_args,
)
from bloqade.pyqrack.task import PyQrackSimulatorTask
from pyqrack.qrack_simulator import QrackSimulator
from bloqade.analysis.address.lattice import UnknownReg, UnknownQubit
from bloqade.analysis.address.analysis import AddressAnalysis

RetType = TypeVar("RetType")
Params = ParamSpec("Params")

DistributionLike: TypeAlias = Union[
    "QuantumState",
    Mapping[Hashable, Real],
    np.ndarray,
    Sequence[Real],
    Iterable[Hashable],
]


def _basis_outcome(outcome: Hashable) -> Hashable:
    """Use integer basis labels for bitstrings and bit vectors."""
    if isinstance(outcome, Integral):
        if outcome < 0:
            raise ValueError("Basis outcomes must be non-negative integers.")
        return int(outcome)

    if isinstance(outcome, str) and outcome and set(outcome) <= {"0", "1"}:
        return int(outcome, 2)

    if isinstance(outcome, (tuple, list, np.ndarray)):
        bits = tuple(outcome)
        if bits and all(
            isinstance(bit, (Integral, np.bool_)) and bit in (0, 1) for bit in bits
        ):
            return int("".join(str(int(bit)) for bit in bits), 2)

    return outcome


def _normalize_weights(weights: Mapping[Hashable, Real]) -> dict[Hashable, float]:
    """Validate and normalize a probability mass function or sample counts."""
    normalized: dict[Hashable, float] = {}
    for outcome, weight in weights.items():
        if not isinstance(weight, Real) or not np.isfinite(weight):
            raise ValueError("Distribution weights must be finite real numbers.")
        if weight < 0:
            raise ValueError("Distribution weights must be non-negative.")
        key = _basis_outcome(outcome)
        normalized[key] = normalized.get(key, 0.0) + float(weight)

    total = sum(normalized.values())
    if total <= 0:
        raise ValueError("A distribution must have positive total weight.")
    return {outcome: weight / total for outcome, weight in normalized.items() if weight}


def _sample_counter(samples: Iterable[Hashable]) -> Counter[Hashable]:
    """Count samples, making list and array bit vectors hashable."""
    return Counter(
        (
            tuple(sample.tolist())
            if isinstance(sample, np.ndarray)
            else tuple(sample) if isinstance(sample, list) else sample
        )
        for sample in samples
    )


def _probability_mass_function(distribution: DistributionLike) -> dict[Hashable, float]:
    """Convert states, probability vectors, mappings, and samples to a PMF."""
    if isinstance(distribution, QuantumState):
        return _probability_mass_function(distribution.probability())

    if isinstance(distribution, Mapping):
        return _normalize_weights(distribution)

    if isinstance(distribution, np.ndarray):
        if distribution.ndim == 1 and np.issubdtype(distribution.dtype, np.floating):
            return _probability_vector(distribution)
        if distribution.ndim == 1 and (
            np.issubdtype(distribution.dtype, np.integer)
            or np.issubdtype(distribution.dtype, np.bool_)
        ):
            if np.all(distribution >= 0) and np.isclose(distribution.sum(), 1.0):
                return _probability_vector(distribution)
            return _normalize_weights(Counter(distribution.tolist()))
        if distribution.ndim == 2:
            return _normalize_weights(Counter(map(tuple, distribution.tolist())))
        raise ValueError(
            "An array distribution must be one-dimensional; use a two-dimensional "
            "array for bit-vector samples."
        )

    if isinstance(distribution, Sequence) and not isinstance(
        distribution, (str, bytes)
    ):
        if all(isinstance(value, Real) for value in distribution):
            probabilities = np.asarray(distribution, dtype=float)
            if any(not isinstance(value, Integral) for value in distribution) or (
                np.all(probabilities >= 0) and np.isclose(probabilities.sum(), 1.0)
            ):
                return _probability_vector(probabilities)
        return _normalize_weights(_sample_counter(distribution))

    if isinstance(distribution, (str, bytes)):
        return _normalize_weights(Counter([distribution]))

    try:
        return _normalize_weights(_sample_counter(distribution))
    except TypeError as error:
        raise ValueError(
            "Samples must be hashable outcomes or bit vectors in a two-dimensional array."
        ) from error


def _probability_vector(probabilities: np.ndarray) -> dict[int, float]:
    """Validate a dense probability vector and convert it to a PMF."""
    probabilities = np.asarray(probabilities, dtype=float)
    if probabilities.ndim != 1 or probabilities.size == 0:
        raise ValueError(
            "A probability distribution must be a non-empty one-dimensional array."
        )
    if not np.all(np.isfinite(probabilities)):
        raise ValueError("Probabilities must be finite real numbers.")
    if np.any(probabilities < -1e-12):
        raise ValueError("Probabilities must be non-negative.")
    probabilities = np.clip(probabilities, 0.0, None)
    if not np.isclose(probabilities.sum(), 1.0, rtol=1e-9, atol=1e-12):
        raise ValueError("Probabilities must sum to one.")
    return {
        index: float(probability)
        for index, probability in enumerate(probabilities)
        if probability
    }


def _aligned_probabilities(
    first: DistributionLike, second: DistributionLike
) -> tuple[np.ndarray, np.ndarray]:
    """Return two probability vectors aligned over the union of their supports."""
    first_pmf = _probability_mass_function(first)
    second_pmf = _probability_mass_function(second)
    outcomes = first_pmf.keys() | second_pmf.keys()
    return (
        np.fromiter((first_pmf.get(outcome, 0.0) for outcome in outcomes), dtype=float),
        np.fromiter(
            (second_pmf.get(outcome, 0.0) for outcome in outcomes), dtype=float
        ),
    )


class QuantumState(NamedTuple):
    """
    A representation of a quantum state as a density matrix, where the density matrix is
    rho = sum_i eigenvalues[i] |eigenvectors[:,i]><eigenvectors[:,i]|.

    This representation is efficient for low-rank density matrices by only storing
    the non-zero eigenvalues and corresponding eigenvectors of the density matrix.
    For example, a pure state has only one non-zero eigenvalue equal to 1.0.

    Endianness and qubit ordering of the state vector is consistent with Cirq, where
    eigenvectors[0,0] corresponds to the amplitude of the |00..000> element of the zeroth eigenvector;
    eigenvectors[1,0] corresponds to the amplitude of the |00..001> element of the zeroth eigenvector;
    eigenvectors[3,0] corresponds to the amplitude of the |00..011> element of the zeroth eigenvector;
    eigenvectors[-1,0] corresponds to the amplitude of the |11..111> element of the zeroth eigenvector.
    A flip of the LAST bit |00..000><00..001| corresponds to applying a PauliX gate to the FIRST qubit.
    A flip of the FIRST bit |00..000><10..000| corresponds to applying a PauliX gate to the LAST qubit.

    Attributes:
        eigenvalues (1d np.ndarray):
            The non-zero eigenvalues of the density matrix.
        eigenvectors (2d np.ndarray):
            The corresponding eigenvectors of the density matrix,
            where eigenvectors[:,i] is the i-th eigenvector.
    Methods:
        Not Implemented, pending https://github.com/QuEraComputing/bloqade-circuit/issues/447
    """

    eigenvalues: np.ndarray
    eigenvectors: np.ndarray

    def canonicalize(self, tol: float = 1e-12) -> "QuantumState":
        """Return an equivalent state in a canonical eigendecomposition."""
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def __add__(self, other: "QuantumState") -> "QuantumState":
        """Return the sum of this state and ``other``."""
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def __mul__(self, scalar: float) -> "QuantumState":
        """Return this state scaled by ``scalar``."""
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    @property
    def dense(self) -> np.ndarray[tuple[int, int], np.complexfloating]:
        """Return the dense density-matrix representation of this state."""
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def __matmul__(self, right: "cirq.Circuit") -> "QuantumState":  # noqa: F821
        """Return the state after applying the Cirq circuit ``right``."""
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def expect(self, operator: Any) -> float:
        """Return the expectation value of ``operator`` in this state."""
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def probability(self) -> np.ndarray[tuple[int], np.floating]:
        """Return computational-basis measurement probabilities.

        The returned vector follows the same basis ordering as ``eigenvectors``:
        index ``i`` is the probability of measuring the basis state ``|i>``.
        """
        eigenvalues = np.asarray(self.eigenvalues, dtype=float)
        eigenvectors = np.asarray(self.eigenvectors, dtype=complex)
        if eigenvalues.ndim != 1 or eigenvectors.ndim != 2:
            raise ValueError(
                "QuantumState eigenvalues and eigenvectors have invalid shapes."
            )
        if eigenvectors.shape[1] != eigenvalues.size:
            raise ValueError(
                "QuantumState must have one eigenvalue for each eigenvector."
            )
        if np.any(eigenvalues < -1e-12):
            raise ValueError("QuantumState eigenvalues must be non-negative.")

        probabilities = np.sum(np.abs(eigenvectors) ** 2 * eigenvalues, axis=1)
        return np.asarray(probabilities.real, dtype=float)

    def variation_distance(self, other: DistributionLike) -> float:
        """Return the variation distance from ``other``.

        ``other`` may be another ``QuantumState``, a dense probability vector,
        a mapping of outcomes to probabilities or counts, or frequentist samples.
        Samples can be bitstrings, integer outcomes, or rows of a two-dimensional
        bit array. Variation distance is equal to total variation distance.
        """
        first, second = _aligned_probabilities(self, other)
        return float(0.5 * np.abs(first - second).sum())

    def total_variation_distance(self, other: DistributionLike) -> float:
        """Return the total variation distance from ``other``.

        This is an alias of :meth:`variation_distance`.
        """
        return self.variation_distance(other)

    def cross_entropy(self, other: DistributionLike) -> float:
        """Return ``H(other, self) = -sum_i q_i log(p_i)``.

        This treats the state as a model and ``other`` as the observed
        distribution, which makes it suitable as an inference loss for raw
        samples. The natural logarithm is used. The result is infinity when
        this state assigns zero probability to an observed outcome.
        """
        model, observed = _aligned_probabilities(self, other)
        positive = observed > 0
        if np.any(model[positive] == 0):
            return float("inf")
        return float(-np.sum(observed[positive] * np.log(model[positive])))

    def kl_divergence(self, other: DistributionLike) -> float:
        """Return ``KL(other || self)`` for computational-basis distributions.

        This treats the state as a model and ``other`` as the observed
        distribution, so ``state.kl_divergence(samples)`` is well-suited to
        model selection. The natural logarithm is used. The result is infinity
        when this state assigns zero probability to an observed outcome.
        """
        model, observed = _aligned_probabilities(self, other)
        positive = observed > 0
        if np.any(model[positive] == 0):
            return float("inf")
        return float(
            np.sum(observed[positive] * np.log(observed[positive] / model[positive]))
        )

    def js_divergence(self, other: DistributionLike) -> float:
        """Return the Jensen-Shannon divergence from ``other``.

        The divergence is symmetric and uses natural logarithms, so its values
        lie in the interval ``[0, log(2)]``.
        """
        first, second = _aligned_probabilities(self, other)
        midpoint = 0.5 * (first + second)
        first_positive = first > 0
        second_positive = second > 0
        return float(
            0.5
            * np.sum(
                first[first_positive]
                * np.log(first[first_positive] / midpoint[first_positive])
            )
            + 0.5
            * np.sum(
                second[second_positive]
                * np.log(second[second_positive] / midpoint[second_positive])
            )
        )

    def bhattacharyya_distance(self, other: DistributionLike) -> float:
        """Return ``-log(sum_i sqrt(p_i q_i))`` from ``other``.

        The result is infinity when the two distributions have disjoint support.
        """
        first, second = _aligned_probabilities(self, other)
        coefficient = np.sqrt(first * second).sum()
        return float("inf") if coefficient == 0 else float(-np.log(coefficient))

    def von_neumann_entropy(self) -> float:
        """Return the von Neumann entropy of this state."""
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    @property
    def qubit_basis(self) -> list[PyQrackQubit]:
        """Return qubits in the order used by this state's computational basis."""
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def reduced_density_matrix(
        self, qubits: list[PyQrackQubit], tol: float = 1e-12
    ) -> "QuantumState":
        """Return the reduced state on ``qubits``."""
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def overlap(self, other: "QuantumState") -> complex:
        """Return the Hilbert-Schmidt overlap with ``other``."""
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )


def _pyqrack_reduced_density_matrix(
    inds: tuple[int, ...], sim_reg: QrackSimulator, tol: float = 1e-12
) -> QuantumState:
    """
    Extract the reduced density matrix representing the state of a list
    of qubits from a PyQRack simulator register.

    Inputs:
        inds: A list of integers labeling the qubit registers to extract the reduced density matrix for
        sim_reg: The PyQRack simulator register to extract the reduced density matrix from
        tol: The tolerance for density matrix eigenvalues to be considered non-zero.
    Outputs:
        An eigh result containing the eigenvalues and eigenvectors of the reduced density matrix.
    """
    # Identify the rest of the qubits in the register
    N = sim_reg.num_qubits()
    other = tuple(set(range(N)).difference(inds))

    if len(set(inds)) != len(inds):
        raise ValueError("Qubits must be unique.")

    if max(inds) > N - 1:
        raise ValueError(
            f"Qubit indices {inds} exceed the number of qubits in the register {N}."
        )

    reordering = inds + other
    # Fix pyqrack edannes to be consistent with Cirq.
    reordering = tuple(N - 1 - x for x in reordering)
    # Extract the statevector from the PyQRack qubits
    statevector = np.array(sim_reg.out_ket())
    # Reshape into a (2,2,2, ..., 2) tensor
    vec_f = np.reshape(statevector, (2,) * N)
    # Reorder the indexes to obey the order of the qubits
    vec_p = np.transpose(vec_f, reordering)
    # Rehape into a 2^N by 2^M matrix to compute the singular value decomposition
    vec_svd = np.reshape(vec_p, (2 ** len(inds), 2 ** len(other)))
    # The singular values and vectors are the eigenspace of the reduced density matrix
    s, v, d = np.linalg.svd(vec_svd, full_matrices=False)

    # Remove the negligible singular values
    nonzero_inds = np.where(np.abs(v) > tol)[0]
    s = s[:, nonzero_inds]
    v = v[nonzero_inds] ** 2
    # Forge into the correct result type
    result = QuantumState(eigenvalues=v, eigenvectors=s)
    return result


@dataclass
class PyQrackSimulatorBase(AbstractSimulatorDevice[PyQrackSimulatorTask]):
    """PyQrack simulation device base class."""

    options: PyQrackOptions = field(default_factory=_default_pyqrack_args)
    """options (PyQrackOptions): options passed into the pyqrack simulator."""

    loss_m_result: MeasurementResultValue = field(
        default=MeasurementResultValue.One, kw_only=True
    )
    rng_state: np.random.Generator = field(
        default_factory=np.random.default_rng, kw_only=True
    )

    MemoryType = TypeVar("MemoryType", bound=MemoryABC)

    def __post_init__(self):
        """Merge supplied simulator options with the default options."""
        self.options = PyQrackOptions({**_default_pyqrack_args(), **self.options})

    def new_task(
        self,
        mt: ir.Method[Params, RetType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        memory: MemoryType,
    ) -> PyQrackSimulatorTask[Params, RetType, MemoryType]:
        """Create an executable PyQrack task for the supplied kernel invocation."""
        interp = PyQrackInterpreter(
            mt.dialects,
            memory=memory,
            rng_state=self.rng_state,
            loss_m_result=self.loss_m_result,
        )
        return PyQrackSimulatorTask(
            kernel=mt, args=args, kwargs=kwargs, pyqrack_interp=interp
        )

    def state_vector(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> list[complex]:
        """Runs task and returns the state vector."""
        return self.task(kernel, args, kwargs).state_vector()

    @staticmethod
    def pauli_expectation(pauli: list[Pauli], qubits: list[PyQrackQubit]) -> float:
        """Returns the expectation value of the given Pauli operator given a list of Pauli operators and qubits.

        Args:
            pauli (list[Pauli]):
                List of Pauli operators to compute the expectation value for.
            qubits (list[PyQrackQubit]):
                List of qubits corresponding to the Pauli operators.

        returns:
            float:
                The expectation value of the Pauli operator.

        """

        if len(pauli) == 0:
            return 0.0

        if len(pauli) != len(qubits):
            raise ValueError("Length of Pauli and qubits must match.")

        sim_reg = qubits[0].sim_reg

        if any(qubit.sim_reg is not sim_reg for qubit in qubits):
            raise ValueError("All qubits must belong to the same simulator register.")

        qubit_ids = [qubit.addr for qubit in qubits]

        if len(qubit_ids) != len(set(qubit_ids)):
            raise ValueError("Qubits must be unique.")

        return sim_reg.pauli_expectation(qubit_ids, pauli)

    @staticmethod
    def quantum_state(
        qubits: list[PyQrackQubit] | IList[PyQrackQubit, Any], tol: float = 1e-12
    ) -> "QuantumState":
        """
        Extract the reduced density matrix representing the state of a list
        of qubits from a PyQRack simulator register.

        Inputs:
            qubits: A list of PyQRack qubits to extract the reduced density matrix for
            tol: The tolerance for density matrix eigenvalues to be considered non-zero.
        Outputs:
            An eigh result containing the eigenvalues and eigenvectors of the reduced density matrix.
        """
        if len(qubits) == 0:
            return QuantumState(
                eigenvalues=np.array([]), eigenvectors=np.array([]).reshape(0, 0)
            )
        sim_reg = qubits[0].sim_reg

        if not all([x.sim_reg is sim_reg for x in qubits]):
            raise ValueError("All qubits must be from the same simulator register.")
        inds: tuple[int, ...] = tuple(qubit.addr for qubit in qubits)

        return _pyqrack_reduced_density_matrix(inds, sim_reg, tol)

    @classmethod
    def reduced_density_matrix(
        cls, qubits: list[PyQrackQubit] | IList[PyQrackQubit, Any], tol: float = 1e-12
    ) -> np.ndarray:
        """
        Extract the reduced density matrix representing the state of a list
        of qubits from a PyQRack simulator register.

        Inputs:
            qubits: A list of PyQRack qubits to extract the reduced density matrix for
            tol: The tolerance for density matrix eigenvalues to be considered non-zero.
        Outputs:
            A dense 2^n x 2^n numpy array representing the reduced density matrix.
        """
        rdm = cls.quantum_state(qubits, tol)
        return np.einsum(
            "ax,x,bx", rdm.eigenvectors, rdm.eigenvalues, rdm.eigenvectors.conj()
        )


@dataclass
class StackMemorySimulator(PyQrackSimulatorBase):
    """
    PyQrack simulator device with preallocated stack of qubits.

    This can be used to simulate kernels where the number of qubits is known
    ahead of time.

    ## Usage examples

    ```
    # Define a kernel
    @qasm2.main
    def main():
        q = qasm2.qreg(2)
        c = qasm2.creg(2)

        qasm2.h(q[0])
        qasm2.cx(q[0], q[1])

        qasm2.measure(q, c)
        return q

    # Create the simulator object
    sim = StackMemorySimulator(min_qubits=2)

    # Execute the kernel
    qubits = sim.run(main)
    ```

    You can also obtain other information from it, such as the state vector:

    ```
    ket = sim.state_vector(main)

    from pyqrack.pauli import Pauli
    expectation_vals = sim.pauli_expectation([Pauli.PauliX, Pauli.PauliI], qubits)
    ```
    """

    min_qubits: int = field(default=0, kw_only=True)

    def task(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ):
        """
        Args:
            kernel (ir.Method):
                The kernel method to run.
            args (tuple[Any, ...]):
                Positional arguments to pass to the kernel method.
            kwargs (dict[str, Any] | None):
                Keyword arguments to pass to the kernel method.

        Returns:
            PyQrackSimulatorTask:
                The task object used to track execution.

        """
        if kwargs is None:
            kwargs = {}

        address_analysis = AddressAnalysis(dialects=kernel.dialects)
        frame, _ = address_analysis.run(kernel)
        if self.min_qubits == 0 and any(
            isinstance(a, (UnknownQubit, UnknownReg)) for a in frame.entries.values()
        ):
            raise ValueError(
                "All addresses must be resolved. Or set min_qubits to a positive integer."
            )

        num_qubits = max(address_analysis.qubit_count, self.min_qubits)
        options = self.options.copy()
        options["qubit_count"] = num_qubits
        memory = StackMemory(
            options,
            total=num_qubits,
        )

        return self.new_task(kernel, args, kwargs, memory)


@dataclass
class DynamicMemorySimulator(PyQrackSimulatorBase):
    """

    PyQrack simulator device with dynamic qubit allocation.

    This can be used to simulate kernels where the number of qubits is not known
    ahead of time.

    ## Usage examples

    ```
    # Define a kernel
    @qasm2.main
    def main():
        q = qasm2.qreg(2)
        c = qasm2.creg(2)

        qasm2.h(q[0])
        qasm2.cx(q[0], q[1])

        qasm2.measure(q, c)
        return q

    # Create the simulator object
    sim = DynamicMemorySimulator()

    # Execute the kernel
    qubits = sim.run(main)
    ```

    You can also obtain other information from it, such as the state vector:

    ```
    ket = sim.state_vector(main)

    from pyqrack.pauli import Pauli
    expectation_vals = sim.pauli_expectation([Pauli.PauliX, Pauli.PauliI], qubits)

    """

    def task(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ):
        """
        Args:
            kernel (ir.Method):
                The kernel method to run.
            args (tuple[Any, ...]):
                Positional arguments to pass to the kernel method.
            kwargs (dict[str, Any] | None):
                Keyword arguments to pass to the kernel method.

        Returns:
            PyQrackSimulatorTask:
                The task object used to track execution.

        """
        if kwargs is None:
            kwargs = {}

        memory = DynamicMemory(self.options.copy())
        return self.new_task(kernel, args, kwargs, memory)
