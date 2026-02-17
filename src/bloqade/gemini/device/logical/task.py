import typing
from typing import TypeVar, ParamSpec
from dataclasses import dataclass

import numpy as np
from kirin import ir
from kirin.rewrite import Walk
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.device import BatchFuture, AbstractRemoteTask
from bloqade.pyqrack import PyQrackSimulatorTask, StackMemorySimulator
from bloqade.gemini.logical.dialects.operations.stmts import TerminalLogicalMeasurement

Param = ParamSpec("Param")
RetType = TypeVar("RetType")


@dataclass
class GeminiLogicalFuture(BatchFuture[RetType]):
    pyqrack_task: PyQrackSimulatorTask
    task_id: str
    shots: int
    n_qubits: int
    postprocessing_function: (
        typing.Callable[[np.ndarray], typing.Iterator[RetType]] | None
    ) = None

    def postprocess(
        self,
        postprocessing_function: (
            typing.Callable[[np.ndarray], typing.Iterator[RetType]] | None
        ),
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
        # NOTE: here's the second part of the hack in the task that removes the
        # terminal measure so pyqrack can run it -- we just extract the logical
        # bit string via measurements

        results = []
        for _ in range(self.shots):
            self.pyqrack_task.run()

            # extract bit string even if there was no return value
            bitstring = []
            for i in range(self.n_qubits):
                bitstring.append(self.pyqrack_task.state.sim_reg.m(i))
            results.append(bitstring)

        # let's just say each logical bit corresponds to 7 physical bits and they all agree
        # TODO: extract the actual physical qubit number
        physical_results = []
        for res in results:
            new_results = []
            for bit in res:
                bit_string = [bit] * 7
                new_results.extend(bit_string)
            physical_results.append(new_results)
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
    postprocessing_function: (
        typing.Callable[[np.ndarray], typing.Iterator[RetType]] | None
    )
    n_qubits: int

    def run_async(self, *, shots: int = 1) -> GeminiLogicalFuture:

        # NOTE: in practice, the actual task and hardware program is submitted here
        # future just stores whatever we need to fetch status & results
        # and post-processing logic

        # NOTE: dirty hack here: just replace terminal measure by measure so pyqrack
        # can run it; this is accounted for when extracting the results in from the future
        execution_kernel_ = self.execution_kernel.similar()
        Walk(_TerminalMeasureToMeasure()).rewrite(execution_kernel_.code)

        # NOTE: for now, just pass in a pyqrack task
        sim = StackMemorySimulator(min_qubits=self.n_qubits)
        pyqrack_task = sim.task(execution_kernel_)

        future = GeminiLogicalFuture(
            pyqrack_task=pyqrack_task, task_id="0", shots=shots, n_qubits=self.n_qubits
        )
        return future.postprocess(self.postprocessing_function)


class _TerminalMeasureToMeasure(RewriteRule):
    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        if not isinstance(node, TerminalLogicalMeasurement):
            return RewriteResult()

        node.delete()
        return RewriteResult(has_done_something=True)
