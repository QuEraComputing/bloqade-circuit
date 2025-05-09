from typing import Any, Generic, TypeVar, ParamSpec, cast
from dataclasses import field, dataclass

import numpy as np
from kirin import ir
from kirin.dialects import py, func

from bloqade.noise import native
from pyqrack.pauli import Pauli
from bloqade.device import AbstractSimulatorDevice
from bloqade.pyqrack.reg import Measurement, PyQrackQubit
from bloqade.pyqrack.base import (
    StackMemory,
    DynamicMemory,
    PyQrackOptions,
    PyQrackInterpreter,
    _default_pyqrack_args,
)
from bloqade.pyqrack.task import PyQrackSimulatorTask, PyQrackNoiseSimulatorTask
from bloqade.qasm2.passes import NoisePass, QASM2Fold, UOpToParallel
from bloqade.analysis.fidelity import FidelityAnalysis
from bloqade.analysis.address.lattice import AnyAddress
from bloqade.analysis.address.analysis import AddressAnalysis

RetType = TypeVar("RetType")
Params = ParamSpec("Params")

PyQrackSimulatorTaskType = TypeVar(
    "PyQrackSimulatorTaskType",
    bound=PyQrackSimulatorTask,
)


@dataclass
class PyQrackSimulatorBase(AbstractSimulatorDevice[PyQrackSimulatorTaskType]):
    options: PyQrackOptions = field(default_factory=_default_pyqrack_args)
    loss_m_result: Measurement = field(default=Measurement.One, kw_only=True)
    rng_state: np.random.Generator = field(
        default_factory=np.random.default_rng, kw_only=True
    )

    def __post_init__(self):
        self.options = PyQrackOptions({**_default_pyqrack_args(), **self.options})

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
class StackMemorySimulator(PyQrackSimulatorBase[PyQrackSimulatorTask]):
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

        pyqrack_interp = PyQrackInterpreter(
            kernel.dialects,
            memory=memory,
            rng_state=self.rng_state,
            loss_m_result=self.loss_m_result,
        )

        return PyQrackSimulatorTask(
            kernel=kernel, args=args, kwargs=kwargs, pyqrack_interp=pyqrack_interp
        )


@dataclass
class DynamicMemorySimulator(PyQrackSimulatorBase[PyQrackSimulatorTask]):
    """PyQrack simulator device with dynamic qubit allocation."""

    def task(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ):
        if kwargs is None:
            kwargs = {}

        pyqrack_interp = PyQrackInterpreter(
            kernel.dialects,
            memory=DynamicMemory(self.options.copy()),
            rng_state=self.rng_state,
            loss_m_result=self.loss_m_result,
        )

        return PyQrackSimulatorTask(
            kernel=kernel,
            args=args,
            kwargs=kwargs,
            pyqrack_interp=pyqrack_interp,
        )


def _arg_closure(
    kernel: ir.Method[Params, RetType], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> ir.Method[..., RetType]:
    """Create a closure for the arguments of the kernel."""

    func_body = ir.Region(block := ir.Block())
    inputs: list[ir.ResultValue] = []
    for arg in args:
        block.stmts.append(const_stmt := py.Constant(arg))
        inputs.append(const_stmt.result)

    kw_names: list[str] = []
    for key, value in kwargs.items():
        block.stmts.append(const_stmt := py.Constant(value))
        kw_names.append(key)
        inputs.append(const_stmt.result)

    block.stmts.append(
        invoke_stmt := func.Invoke(
            inputs=tuple(inputs),
            callee=kernel,
            kwargs=tuple(kw_names),
            purity=False,
        )
    )
    block.stmts.append(func.Return(invoke_stmt.result))

    code = func.Function(
        sym_name="closure",
        signature=func.Signature((), kernel.return_type),
        body=func_body,
    )
    return ir.Method(None, None, "closure", [], kernel.dialects, code)


NoiseModelType = TypeVar("NoiseModelType", bound=native.MoveNoiseModelABC)


@dataclass
class NoiseSimulator(
    PyQrackSimulatorBase[PyQrackNoiseSimulatorTask], Generic[NoiseModelType]
):
    noise_model: NoiseModelType = field(default_factory=native.TwoRowZoneModel)
    gate_noise_params: native.GateNoiseParams = field(
        default_factory=native.GateNoiseParams
    )
    optimize_parallel_gates: bool = field(default=True, kw_only=True)
    decompose_native_gates: bool = field(default=True, kw_only=True)

    def _compile_kernel(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> ir.Method[[], RetType]:
        if len(args) > 0 or len(kwargs) > 0:
            folded_kernel = _arg_closure(kernel, args, kwargs)
            args = ()
            kwargs = {}
        else:
            folded_kernel = cast(ir.Method[..., RetType], kernel)

        QASM2Fold(folded_kernel.dialects).fixpoint(folded_kernel)

        if self.optimize_parallel_gates:
            UOpToParallel(
                folded_kernel.dialects,
                rewrite_to_native_first=self.decompose_native_gates,
            )(folded_kernel)

        if native.dialect not in folded_kernel.dialects:
            noise_pass = NoisePass(
                kernel.dialects,
                self.noise_model,
                self.gate_noise_params,
            )

            noise_pass(folded_kernel)
            folded_kernel = folded_kernel.similar(
                folded_kernel.dialects.add(native.dialect)
            )

        return folded_kernel

    def task(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ):
        if kwargs is None:
            kwargs = {}

        folded_kernel = self._compile_kernel(kernel, args, kwargs)

        pyqrack_interp = PyQrackInterpreter(
            folded_kernel.dialects,
            memory=DynamicMemory(self.options.copy()),
            rng_state=self.rng_state,
            loss_m_result=self.loss_m_result,
        )

        return PyQrackNoiseSimulatorTask(
            kernel=folded_kernel,
            args=args,
            kwargs=kwargs,
            pyqrack_interp=pyqrack_interp,
            fidelity_scorer=FidelityAnalysis(kernel.dialects),
        )
