from typing import TypeVar, ParamSpec, cast
from dataclasses import dataclass

import numpy as np

from bloqade.task import AbstractSimulatorTask
from bloqade.pyqrack.base import (
    MemoryABC,
    PyQrackInterpreter,
)
from bloqade.analysis.fidelity import FidelityAnalysis

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


@dataclass
class PyQrackNoiseSimulatorTask(PyQrackSimulatorTask[Param, RetType, MemoryType]):
    """PyQrack noise simulator task for Bloqade."""

    fidelity_scorer: FidelityAnalysis

    @dataclass(frozen=True)
    class FidelityResult:
        """Stores the results of the fidelity analysis."""

        gate_fidelity: float
        """The global fidelity of the circuit execution."""
        atom_survival_probability: list[float]
        """The survival probability of each qubit in the circuit."""

        @property
        def typical_survival_probability(self) -> float:
            """Returns the typical survival probability of the qubits."""
            return float(np.median(self.atom_survival_probability))

    def run(self) -> RetType:
        return self.pyqrack_interp.run(
            self.kernel,
            args=self.args,
            kwargs=self.kwargs,
        )

    def fidelity(self) -> FidelityResult:
        _, _ = self.fidelity_scorer.run_analysis(self.kernel)

        return self.FidelityResult(
            self.fidelity_scorer.gate_fidelity,
            self.fidelity_scorer.atom_survival_probability,
        )
