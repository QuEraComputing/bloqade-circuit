import abc
import typing
from dataclasses import field, dataclass
from unittest.mock import Mock

import numpy as np
from kirin.interp import Interpreter
from typing_extensions import Self
from kirin.interp.exceptions import InterpreterError

from bloqade.qrb.reg import MeasurementResultValue

if typing.TYPE_CHECKING:
    from qrackbind import QrackSimulator


class QRBOptions(typing.TypedDict):
    qubitCount: int
    isTensorNetwork: bool
    isSchmidtDecomposeMulti: bool
    isSchmidtDecompose: bool
    isStabilizerHybrid: bool
    isBinaryDecisionTree: bool
    isPaged: bool
    isCpuGpuHybrid: bool
    isOpenCL: bool


def _validate_qrb_options(options: QRBOptions) -> None:
    if options["isBinaryDecisionTree"] and options["isStabilizerHybrid"]:
        raise ValueError(
            "Cannot use both isBinaryDecisionTree and isStabilizerHybrid at the same time."
        )
    elif options["isTensorNetwork"] and options["isBinaryDecisionTree"]:
        raise ValueError(
            "Cannot use both isTensorNetwork and isBinaryDecisionTree at the same time."
        )
    elif options["isTensorNetwork"] and options["isStabilizerHybrid"]:
        raise ValueError(
            "Cannot use both isTensorNetwork and isStabilizerHybrid at the same time."
        )


def _default_qrb_args() -> QRBOptions:
    return QRBOptions(
        qubitCount=-1,
        isTensorNetwork=False,
        isSchmidtDecomposeMulti=True,
        isSchmidtDecompose=True,
        isStabilizerHybrid=False,
        isBinaryDecisionTree=False,
        isPaged=True,
        isCpuGpuHybrid=True,
        isOpenCL=True,
    )


@dataclass
class MemoryABC(abc.ABC):
    qrb_options: QRBOptions = field(default_factory=_default_qrb_args)
    sim_reg: "QrackSimulator" = field(init=False)

    def __post_init__(self):
        _validate_qrb_options(self.qrb_options)

    @abc.abstractmethod
    def allocate(self, n_qubits: int) -> tuple[int, ...]:
        """Allocate `n_qubits` qubits and return their ids."""
        ...

    def reset(self):
        """Reset the memory, releasing all qubits."""
        from qrackbind import QrackSimulator

        # do not reset the simulator it might be used by
        # results of the simulation
        self.sim_reg = QrackSimulator(**self.qrb_options)


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

        is_tensor_network = self.qrb_options.get("isTensorNetwork", False)
        if is_tensor_network:
            raise ValueError("DynamicMemory does not support tensor networks")

    def allocate(self, n_qubits: int):
        # qrackbind: allocate_qubits(n) allocates n new qubits and returns
        # the index of the first newly allocated qubit.
        start = self.sim_reg.allocate_qubits(n_qubits)
        return tuple(range(start, start + n_qubits))


MemoryType = typing.TypeVar("MemoryType", bound=MemoryABC)


@dataclass
class QRBInterpreter(Interpreter, typing.Generic[MemoryType]):
    keys = ["qrb", "main"]
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
