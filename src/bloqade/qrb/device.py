from typing import Any, TypeVar, ParamSpec, NamedTuple
from dataclasses import field, dataclass

import numpy as np
from kirin import ir
from kirin.dialects.ilist import IList

from bloqade.device import AbstractSimulatorDevice
from bloqade.qrb.reg import QRBQubit, MeasurementResultValue
from bloqade.qrb.base import (
    MemoryABC,
    StackMemory,
    DynamicMemory,
    QRBOptions,
    QRBInterpreter,
    _default_qrb_args,
)
from bloqade.qrb.task import QRBSimulatorTask
from bloqade.analysis.address.lattice import UnknownReg, UnknownQubit
from bloqade.analysis.address.analysis import AddressAnalysis

RetType = TypeVar("RetType")
Params = ParamSpec("Params")


class QuantumState(NamedTuple):
    """
    A representation of a quantum state as a density matrix.

    rho = sum_i eigenvalues[i] |eigenvectors[:,i]><eigenvectors[:,i]|

    Attributes:
        eigenvalues (1d np.ndarray):
            The non-zero eigenvalues of the density matrix.
        eigenvectors (2d np.ndarray):
            The corresponding eigenvectors of the density matrix,
            where eigenvectors[:,i] is the i-th eigenvector.
    """

    eigenvalues: np.ndarray
    eigenvectors: np.ndarray

    def canonicalize(self, tol: float = 1e-12) -> "QuantumState":
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def __add__(self, other: "QuantumState") -> "QuantumState":
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def __mul__(self, scalar: float) -> "QuantumState":
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def expect(self, operator: Any) -> float:
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def probability(self) -> np.ndarray[tuple[int], np.floating]:
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def von_neumann_entropy(self) -> float:
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    @property
    def qubit_basis(self) -> list[QRBQubit]:
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def reduced_density_matrix(
        self, qubits: list[QRBQubit], tol: float = 1e-12
    ) -> "QuantumState":
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )

    def overlap(self, other: "QuantumState") -> complex:
        raise NotImplementedError(
            "https://github.com/QuEraComputing/bloqade-circuit/issues/447"
        )


def _qrb_reduced_density_matrix(
    inds: tuple[int, ...], sim_reg: Any, tol: float = 1e-12
) -> QuantumState:
    """Extract the reduced density matrix from a qrackbind simulator register."""
    # qrackbind: num_qubits is a property, not a method
    N = sim_reg.num_qubits
    other = tuple(set(range(N)).difference(inds))

    if len(set(inds)) != len(inds):
        raise ValueError("Qubits must be unique.")

    if max(inds) > N - 1:
        raise ValueError(
            f"Qubit indices {inds} exceed the number of qubits in the register {N}."
        )

    reordering = inds + other
    # Fix qrackbind endianness to be consistent with Cirq.
    reordering = tuple(N - 1 - x for x in reordering)
    # qrackbind: state_vector is a property returning np.ndarray
    statevector = np.array(sim_reg.state_vector)
    vec_f = np.reshape(statevector, (2,) * N)
    vec_p = np.transpose(vec_f, reordering)
    vec_svd = np.reshape(vec_p, (2 ** len(inds), 2 ** len(other)))
    s, v, d = np.linalg.svd(vec_svd, full_matrices=False)
    nonzero_inds = np.where(np.abs(v) > tol)[0]
    s = s[:, nonzero_inds]
    v = v[nonzero_inds] ** 2
    return QuantumState(eigenvalues=v, eigenvectors=s)


@dataclass
class QRBSimulatorBase(AbstractSimulatorDevice[QRBSimulatorTask]):
    """qrackbind simulation device base class."""

    options: QRBOptions = field(default_factory=_default_qrb_args)
    loss_m_result: MeasurementResultValue = field(
        default=MeasurementResultValue.One, kw_only=True
    )
    rng_state: np.random.Generator = field(
        default_factory=np.random.default_rng, kw_only=True
    )

    MemoryType = TypeVar("MemoryType", bound=MemoryABC)

    def __post_init__(self):
        self.options = QRBOptions({**_default_qrb_args(), **self.options})

    def new_task(
        self,
        mt: ir.Method[Params, RetType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        memory: "MemoryABC",
    ) -> QRBSimulatorTask:
        interp = QRBInterpreter(
            mt.dialects,
            memory=memory,
            rng_state=self.rng_state,
            loss_m_result=self.loss_m_result,
        )
        return QRBSimulatorTask(kernel=mt, args=args, kwargs=kwargs, qrb_interp=interp)

    def state_vector(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> list[complex]:
        """Runs task and returns the state vector."""
        return self.task(kernel, args, kwargs).state_vector()

    @staticmethod
    def pauli_expectation(pauli: list, qubits: list[QRBQubit]) -> float:
        """Returns the expectation value of a Pauli operator across a list of qubits."""
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
        # qrackbind: exp_val_pauli(paulis, qubits) — note arg order vs pyqrack
        return sim_reg.exp_val_pauli(pauli, qubit_ids)

    @staticmethod
    def quantum_state(
        qubits: list[QRBQubit] | IList[QRBQubit, Any], tol: float = 1e-12
    ) -> "QuantumState":
        """Extract the reduced density matrix for a list of qrackbind qubits."""
        if len(qubits) == 0:
            return QuantumState(
                eigenvalues=np.array([]), eigenvectors=np.array([]).reshape(0, 0)
            )
        sim_reg = qubits[0].sim_reg
        if not all([x.sim_reg is sim_reg for x in qubits]):
            raise ValueError("All qubits must be from the same simulator register.")
        inds: tuple[int, ...] = tuple(qubit.addr for qubit in qubits)
        return _qrb_reduced_density_matrix(inds, sim_reg, tol)

    @classmethod
    def reduced_density_matrix(
        cls, qubits: list[QRBQubit] | IList[QRBQubit, Any], tol: float = 1e-12
    ) -> np.ndarray:
        """Extract the reduced density matrix as a dense numpy array."""
        rdm = cls.quantum_state(qubits, tol)
        return np.einsum(
            "ax,x,bx", rdm.eigenvectors, rdm.eigenvalues, rdm.eigenvectors.conj()
        )


@dataclass
class StackMemorySimulator(QRBSimulatorBase):
    """qrackbind simulator device with preallocated stack of qubits."""

    min_qubits: int = field(default=0, kw_only=True)

    def task(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ):
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
        options["qubitCount"] = num_qubits
        memory = StackMemory(options, total=num_qubits)
        return self.new_task(kernel, args, kwargs, memory)


@dataclass
class DynamicMemorySimulator(QRBSimulatorBase):
    """qrackbind simulator device with dynamic qubit allocation."""

    def task(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ):
        if kwargs is None:
            kwargs = {}
        memory = DynamicMemory(self.options.copy())
        return self.new_task(kernel, args, kwargs, memory)
