import typing
from typing import TypeVar, ParamSpec
from dataclasses import dataclass

import numpy as np
from kirin import ir

from bloqade.device import BatchFuture, AbstractRemoteTask
from bloqade.pyqrack import PyQrackSimulatorTask, StackMemorySimulator

Param = ParamSpec("Param")
RetType = TypeVar("RetType")


@dataclass
class GeminiLogicalFuture(BatchFuture[RetType]):
    pyqrack_task: PyQrackSimulatorTask
    task_id: str
    shots: int
    postprocessing_function: (
        typing.Callable[[np.ndarray], typing.Iterator[RetType]] | None
    ) = None
    n_qubits: int = 10

    def postprocess(
        self,
        postprocessing_function: typing.Callable[
            [np.ndarray], typing.Iterator[RetType]
        ],
    ) -> "GeminiLogicalFuture":
        self.postprocessing_function = postprocessing_function
        return self

    def result(
        self,
        timeout: float | None = None,
    ) -> list[RetType]:
        # TODO: actually fetch results
        physical_results = self._physical_result(timeout=timeout)
        return list(self._postprocess_results(physical_results))

    def _physical_result(self, timeout: float | None = None) -> np.ndarray:
        results = []
        for _ in range(self.shots):
            self.pyqrack_task.run()

            # extract bit string even if there was no return value
            bitstring = []
            for i in range(self.n_qubits):
                bitstring.append(self.pyqrack_task.state.sim_reg.m(i))
            results.append(bitstring)

        # let's just say each logical bit corresponds to 17 physical bits and they all agree
        physical_results = []
        for res in results:
            new_bitstring = []
            for bit in res:
                new_bitstring.extend([bit] * 17)
            physical_results.append(new_bitstring)
        return np.array(physical_results)

    def partial_result(self) -> list[RetType]:
        # TODO
        return self.result()

    def _postprocess_results(self, physical_results) -> typing.Iterator[RetType]:
        if self.postprocessing_function is None:
            raise ValueError("No post-processing logic! Results are empty")

        return self.postprocessing_function(physical_results)

    def fetch(self) -> None:
        # TODO
        pass

    def cancel(self):
        """Attempts to cancel the execution of the future."""
        pass

    def cancelled(self) -> bool:
        return False

    def done(self) -> bool:
        return False


@dataclass
class GeminiLogicalTask(AbstractRemoteTask[Param, RetType]):
    execution_kernel: ir.Method[Param, None]
    postprocessing_function: typing.Callable[[np.ndarray], typing.Iterator[RetType]]
    n_qubits: int = 10

    def run_async(self, *, shots: int = 1) -> GeminiLogicalFuture:

        # NOTE: in practice, the actual task and hardware program is submitted here
        # future just stores whatever we need to fetch status & results
        # and post-processing logic

        # NOTE: for now, just pass in a pyqrack task
        sim = StackMemorySimulator(min_qubits=self.n_qubits)
        pyqrack_task = sim.task(self.execution_kernel)

        future = GeminiLogicalFuture(
            pyqrack_task=pyqrack_task, task_id="0", shots=shots
        )
        return future.postprocess(self.postprocessing_function)
