from typing import TypeVar, ParamSpec, cast
from collections import Counter
from dataclasses import dataclass

import numpy as np
from kirin.dialects.ilist import IList

from bloqade.task import AbstractSimulatorTask
from bloqade.pyqrack.reg import QubitState, PyQrackQubit
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

    def qubits(self) -> list[PyQrackQubit]:
        """Returns the qubits in the simulator."""
        try:
            N = self.state.sim_reg.num_qubits()
            return [
                PyQrackQubit(
                    addr=i, sim_reg=self.state.sim_reg, state=QubitState.Active
                )
                for i in range(N)
            ]
        except AttributeError:
            Warning("Task has not been run, there are no qubits!")
            return []

    def multirun(self, shots: int = 1) -> dict[RetType, float]:
        """
        Repeatedly run the task to collect statistics on the shot outcomes
          The average is done over nshots and thus is frequentist and converges to
          exact only in the shots -> infinity limit.
        Parameters:
        shots - the number of repetitions of the task
        Returns:
        dict[RetType, float] - a dictionary mapping outcomes to their probabilities,
          as estimated from counting the shot outcomes. RetType must be hashable.
        """

        results: list[RetType] = [self.run() for _ in range(shots)]

        # Convert IList to tuple so that it is hashable by Counter
        def convert(data):
            if isinstance(data, (list, IList)):
                return tuple(convert(item) for item in data)
            return data

        results = convert(results)

        data = {
            key: value / len(results) for key, value in Counter(results).items()
        }  # Normalize to probabilities
        return data

    def multistate(
        self, shots: int = 1, selector: None = None
    ) -> "np.linalg._linalg.EighResult":
        """
        Repeatedly run the task to extract the averaged quantum state.
          The average is done over nshots and thus is frequentist and converges to
          exact only in the shots -> infinity limit.
        Parameters:
        shots - the number of repetitions of the task
        selector - an optional callable that takes the output of self.run() and extract
          the [returned] qubits to be used for the quantum state. If None, all qubits
          in the simulator are used. Other shan selector = None, the common other pattern is
           > selector = lambda qubits: qubits
          for the case where self.run() returns a list of qubits, or
           > selector = lambda qubit: [qubits]
          when the output is a single qubit.
        Returns:
        np.linalg._linalg.EighResult - the averaged quantum state as a density matrix,
          represented in its eigenbasis.
        """
        # Import here to avoid circular dependencies.
        from bloqade.pyqrack.device import PyQrackSimulatorBase

        states = []
        for _ in range(shots):
            res = self.run()
            if callable(selector):
                qbs = selector(res)
            else:
                qbs = self.qubits()
            states.append(PyQrackSimulatorBase.quantum_state(qbs))

        state = np.linalg._linalg.EighResult(
            eigenvectors=np.concatenate(
                [state.eigenvectors for state in states], axis=1
            ),
            eigenvalues=np.concatenate([state.eigenvalues for state in states], axis=0)
            / len(states),
        )

        # Canonicalize the state by orthoganalizing the basis vectors.
        tol = 1e-7
        s, v, d = np.linalg.svd(
            state.eigenvectors * np.sqrt(state.eigenvalues), full_matrices=False
        )
        mask = v > tol
        v = v[mask] ** 2
        s = s[:, mask]
        return np.linalg._linalg.EighResult(eigenvalues=v, eigenvectors=s)
