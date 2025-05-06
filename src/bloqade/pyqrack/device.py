from typing import Any, TypeVar, ParamSpec
from dataclasses import field, dataclass

import numpy as np
from kirin import ir

from pyqrack.pauli import Pauli
from bloqade.device import AbstractSimulatorDevice
from bloqade.pyqrack.reg import Measurement, PyQrackQubit
from bloqade.pyqrack.base import (
    MemoryABC,
    StackMemory,
    DynamicMemory,
    PyQrackOptions,
    PyQrackInterpreter,
    _default_pyqrack_args,
)
from bloqade.pyqrack.task import PyQrackSimulatorTask
from bloqade.analysis.address.lattice import AnyAddress
from bloqade.analysis.address.analysis import AddressAnalysis

RetType = TypeVar("RetType")
Params = ParamSpec("Params")


@dataclass
class PyQrackSimulatorBase(AbstractSimulatorDevice[PyQrackSimulatorTask]):
    options: PyQrackOptions = field(default_factory=_default_pyqrack_args)
    loss_m_result: Measurement = field(default=Measurement.One, kw_only=True)
    rng_state: np.random.Generator = field(
        default_factory=np.random.default_rng, kw_only=True
    )

    MemoryType = TypeVar("MemoryType", bound=MemoryABC)

    def __post_init__(self):
        self.options = PyQrackOptions({**_default_pyqrack_args(), **self.options})

    def new_task(
        self,
        mt: ir.Method[Params, RetType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        memory: MemoryType,
    ) -> PyQrackSimulatorTask[Params, RetType, MemoryType]:
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
        task = self.task(kernel, args, kwargs)
        task.run()
        return task.state.sim_reg.out_ket()

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

        return sim_reg.pauli_expectation(pauli, qubit_ids)


@dataclass
class StackMemorySimulator(PyQrackSimulatorBase):
    """PyQrack simulator device with precalculated stack of qubits."""

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
        frame, _ = address_analysis.run_analysis(kernel)
        if self.min_qubits == 0 and any(
            isinstance(a, AnyAddress) for a in frame.entries.values()
        ):
            raise ValueError(
                "All addresses must be resolved. Or set min_qubits to a positive integer."
            )

        num_qubits = max(address_analysis.qubit_count, self.min_qubits)
        options = self.options.copy()
        options["qubitCount"] = num_qubits
        memory = StackMemory(
            options,
            total=num_qubits,
        )

        return self.new_task(kernel, args, kwargs, memory)


@dataclass
class DynamicMemorySimulator(PyQrackSimulatorBase):
    """PyQrack simulator device with dynamic qubit allocation."""

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


def test():
    from bloqade.qasm2 import extended

    @extended
    def main():
        return 1

    @extended
    def obs(result: int) -> int:
        return result

    res = DynamicMemorySimulator().task(main)
    return res.run()
