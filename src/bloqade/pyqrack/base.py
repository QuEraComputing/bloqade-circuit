import abc
import typing
from dataclasses import field, dataclass
from unittest.mock import Mock

import numpy as np
from kirin.interp import Interpreter
from typing_extensions import Self
from kirin.interp.exceptions import InterpreterError

from bloqade.pyqrack.reg import MeasurementResultValue

if typing.TYPE_CHECKING:
    from pyqrack import QrackSimulator


class PyQrackOptions(typing.TypedDict, total=False):
    qubit_count: int
    clone_sid: int
    is_schmidt_decompose_multi: bool
    is_stabilizer_hybrid: bool
    is_binary_decision_tree: bool
    is_gpu: bool
    is_host_pointer: bool
    is_sparse: bool
    is_near_clifford_tableau_writer: bool
    noise: int
    pyzx_circuit: typing.Any
    qiskit_circuit: typing.Any


def _validate_pyqrack_options(options: PyQrackOptions) -> None:
    if options.get("is_binary_decision_tree") and options.get("is_stabilizer_hybrid"):
        raise ValueError(
            "Cannot use both is_binary_decision_tree and is_stabilizer_hybrid "
            "at the same time."
        )


def _default_pyqrack_args() -> PyQrackOptions:
    return PyQrackOptions(
        qubit_count=-1,
        is_schmidt_decompose_multi=True,
        is_stabilizer_hybrid=False,
        is_binary_decision_tree=False,
        is_gpu=True,
    )


@dataclass
class MemoryABC(abc.ABC):
    pyqrack_options: PyQrackOptions = field(default_factory=_default_pyqrack_args)
    sim_reg: "QrackSimulator" = field(init=False)

    def __post_init__(self):
        _validate_pyqrack_options(self.pyqrack_options)

    @abc.abstractmethod
    def allocate(self, n_qubits: int) -> tuple[int, ...]:
        """Allocate `n_qubits` qubits and return their ids."""
        ...

    def reset(self):
        """Reset the memory, releasing all qubits."""
        from pyqrack import QrackSimulator

        # do not reset the simulator it might be used by
        # results of the simulation
        self.sim_reg = QrackSimulator(**self.pyqrack_options)


@dataclass
class MockMemory(MemoryABC):
    """Mock memory for testing purposes."""

    allocated: int = field(init=False, default=0)

    def allocate(self, n_qubits: int):
        allocated = self.allocated + n_qubits
        result = tuple(range(self.allocated, allocated))
        self.allocated = allocated
        return result

    def reset(self):
        self.allocated = 0
        self.sim_reg = Mock()


@dataclass
class StackMemory(MemoryABC):
    total: int = field(kw_only=True)
    allocated: int = field(init=False, default=0)

    def allocate(self, n_qubits: int):
        curr_allocated = self.allocated
        self.allocated += n_qubits

        if self.allocated > self.total:
            raise InterpreterError(
                f"qubit allocation exceeds memory, "
                f"{self.total} qubits, "
                f"{self.allocated} allocated"
            )

        return tuple(range(curr_allocated, self.allocated))

    def reset(self):
        super().reset()
        self.allocated = 0


@dataclass
class DynamicMemory(MemoryABC):
    def __post_init__(self):
        self.reset()

    def allocate(self, n_qubits: int):
        start = self.sim_reg.num_qubits()
        for i in range(start, start + n_qubits):
            self.sim_reg.allocate_qubit(i)

        return tuple(range(start, start + n_qubits))


MemoryType = typing.TypeVar("MemoryType", bound=MemoryABC)


@dataclass
class PyQrackInterpreter(Interpreter, typing.Generic[MemoryType]):
    keys = ["pyqrack", "main"]
    memory: MemoryType = field(kw_only=True)
    rng_state: np.random.Generator = field(
        default_factory=np.random.default_rng, kw_only=True
    )
    loss_m_result: MeasurementResultValue = field(
        default=MeasurementResultValue.One, kw_only=True
    )
    """The value of a measurement result when a qubit is lost."""

    global_measurement_id: int = field(init=False, default=0)

    def initialize(self) -> Self:
        super().initialize()
        self.memory.reset()  # reset allocated qubits
        return self

    def set_global_measurement_id(self, m: MeasurementResultValue):
        m.measurement_id = self.global_measurement_id
        self.global_measurement_id += 1
