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
    """PyQrack simulation device base class."""

    options: PyQrackOptions = field(default_factory=_default_pyqrack_args)
    """options (PyQrackOptions): options passed into the pyqrack simulator."""

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
        return self.task(kernel, args, kwargs).state_vector()

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

        return sim_reg.pauli_expectation(qubit_ids, pauli)


@dataclass
class StackMemorySimulator(PyQrackSimulatorBase):
    """
    PyQrack simulator device with preallocated stack of qubits.

    This can be used to simulate kernels where the number of qubits is known
    ahead of time.

    ## Usage examples

    ```
    # Define a kernel
    @qasm2.main
    def main():
        q = qasm2.qreg(2)
        c = qasm2.creg(2)

        qasm2.h(q[0])
        qasm2.cx(q[0], q[1])

        qasm2.measure(q, c)
        return q

    # Create the simulator object
    sim = StackMemorySimulator(min_qubits=2)

    # Execute the kernel
    qubits = sim.run(main)
    ```

    You can also obtain other information from it, such as the state vector:

    ```
    ket = sim.state_vector(main)

    from pyqrack.pauli import Pauli
    expectation_vals = sim.pauli_expectation([Pauli.PauliX, Pauli.PauliI], qubits)
    ```
    """

    min_qubits: int = field(default=0, kw_only=True)

    def task(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ):
        """
        Args:
            kernel (ir.Method):
                The kernel method to run.
            args (tuple[Any, ...]):
                Positional arguments to pass to the kernel method.
            kwargs (dict[str, Any] | None):
                Keyword arguments to pass to the kernel method.

        Returns:
            PyQrackSimulatorTask:
                The task object used to track execution.

        """
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
    """

    PyQrack simulator device with dynamic qubit allocation.

    This can be used to simulate kernels where the number of qubits is not known
    ahead of time.

    ## Usage examples

    ```
    # Define a kernel
    @qasm2.main
    def main():
        q = qasm2.qreg(2)
        c = qasm2.creg(2)

        qasm2.h(q[0])
        qasm2.cx(q[0], q[1])

        qasm2.measure(q, c)
        return q

    # Create the simulator object
    sim = DynamicMemorySimulator()

    # Execute the kernel
    qubits = sim.run(main)
    ```

    You can also obtain other information from it, such as the state vector:

    ```
    ket = sim.state_vector(main)

    from pyqrack.pauli import Pauli
    expectation_vals = sim.pauli_expectation([Pauli.PauliX, Pauli.PauliI], qubits)

    """

    def task(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ):
        """
        Args:
            kernel (ir.Method):
                The kernel method to run.
            args (tuple[Any, ...]):
                Positional arguments to pass to the kernel method.
            kwargs (dict[str, Any] | None):
                Keyword arguments to pass to the kernel method.

        Returns:
            PyQrackSimulatorTask:
                The task object used to track execution.

        """
        if kwargs is None:
            kwargs = {}

        memory = DynamicMemory(self.options.copy())
        return self.new_task(kernel, args, kwargs, memory)
