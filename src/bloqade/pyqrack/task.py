from typing import TypeVar, ParamSpec, cast
from dataclasses import dataclass

from bloqade.task import AbstractSimulatorTask
from bloqade.pyqrack.base import (
    MemoryABC,
    PyQrackInterpreter,
)

RetType = TypeVar("RetType")
Param = ParamSpec("Param")
MemoryType = TypeVar("MemoryType", bound=MemoryABC)


@dataclass
class PyQrackSimulatorTask(AbstractSimulatorTask[Param, RetType, MemoryType]):
    """PyQrack simulator task for Bloqade."""

    pyqrack_interp: PyQrackInterpreter[MemoryType]

    def run(self) -> RetType:
        return cast(
            RetType,
            self.pyqrack_interp.run(
                self.kernel,
                args=self.args,
                kwargs=self.kwargs,
            ),
        )

    @property
    def state(self) -> MemoryType:
        return self.pyqrack_interp.memory

    def state_vector(self) -> list[complex]:
        """Returns the state vector of the simulator."""
        self.run()
        return self.state.sim_reg.out_ket()
