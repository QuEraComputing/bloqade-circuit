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

    def batch_run(self, shots: int = 1) -> dict[RetType, float]:
        """
        Repeatedly run the task to collect statistics on the shot outcomes.
        The average is done over [shots] repetitions and thus is frequentist
        and converges to exact only in the shots -> infinity limit.

        Args:
            shots (int):
                the number of repetitions of the task
        Returns:
            dict[RetType, float]:
                a dictionary mapping outcomes to their probabilities,
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

    def batch_state(
        self, shots: int = 1, qubit_map: None = None
    ) -> "QuantumState":  # noqa: F821
        """
        Repeatedly run the task to extract the averaged quantum state.
        The average is done over [shots] repetitions and thus is frequentist
        and converges to exact only in the shots -> infinity limit.

        Args:
            shots (int):
                the number of repetitions of the task
            qubit_map (callable | None):
                an optional callable that takes the output of self.run() and extract
                the [returned] qubits to be used for the quantum state.
                If None, all qubits in the simulator are used, in the order set by the simulator.
                If callable, qubit_map must have the signature
                > qubit_map(output:RetType) -> list[PyQrackQubit]
                and the averaged state is
                > quantum_state(qubit_map(self.run())).
                If qubit_map is not None, self.run() must return qubit(s).
                Two common patterns here are:
                 > qubit_map = lambda qubits: qubits
                for the case where self.run() returns a list of qubits, or
                 > qubit_map = lambda qubit: [qubits]
                for the case where self.run() returns a single qubit.
        Returns:
            QuantumState:
                the averaged quantum state as a density matrix,
                represented in its eigenbasis.
        """
        # Import here to avoid circular dependencies.
        from bloqade.pyqrack.device import QuantumState, PyQrackSimulatorBase

        states: list[QuantumState] = []
        for _ in range(shots):
            res = self.run()
            if callable(qubit_map):
                qbs = qubit_map(res)
            else:
                qbs = self.qubits()
            states.append(PyQrackSimulatorBase.quantum_state(qbs))

        state = QuantumState(
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
        return QuantumState(eigenvalues=v, eigenvectors=s)
