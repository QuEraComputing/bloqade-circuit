from __future__ import annotations

import io
from types import ModuleType
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar, ClassVar, overload
from dataclasses import field, dataclass

import numpy as np
from kirin import ir

from bloqade.stim import groups as bloqade_stim
from bloqade.task import AbstractSimulatorTask
from bloqade.device import AbstractSimulatorDevice
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass

if TYPE_CHECKING:
    from typing import Protocol

    class CompiledSampler(Protocol):
        """Protocol for compiled samplers (stim/tsim)."""

        def sample(
            self,
            shots: int,
            **kwargs: Any,
        ) -> tuple[np.ndarray, np.ndarray] | np.ndarray: ...


TaskType = TypeVar("TaskType", bound="SamplingTaskBase")


def _codegen(mt: ir.Method) -> str:
    """Compile a kernel to STIM program string.

    Args:
        mt: The kernel method to compile. Must have no arguments.

    Returns:
        The STIM program as a string.
    """
    # Create a copy to avoid mutating original
    mt = mt.similar()

    SquinToStimPass(mt.dialects)(mt)

    buf = io.StringIO()
    emit = EmitStimMain(dialects=bloqade_stim.main, io=buf)
    emit.initialize()
    emit.run(mt)
    return buf.getvalue().strip()


@dataclass
class SamplingTaskBase(AbstractSimulatorTask[[], np.ndarray, "CompiledSampler"]):
    """Base task for sampling from a compiled STIM or TSIM circuit."""

    sampler: CompiledSampler
    program_text: str
    sample_detectors: bool

    _supports_batch_size: ClassVar[bool] = True

    @overload
    def run(
        self,
        *,
        shots: int = 100_000,
        batch_size: int | None = None,
        prepend_observables: bool = False,
        append_observables: bool = False,
        separate_observables: Literal[True],
    ) -> tuple[np.ndarray, np.ndarray]: ...

    @overload
    def run(
        self,
        *,
        shots: int = 100_000,
        batch_size: int | None = None,
        prepend_observables: bool = False,
        append_observables: bool = False,
        separate_observables: Literal[False],
    ) -> np.ndarray: ...

    def run(
        self,
        *,
        shots: int = 100_000,
        batch_size: int | None = None,
        prepend_observables: bool = False,
        append_observables: bool = False,
        separate_observables: bool = False,
    ) -> tuple[np.ndarray, np.ndarray] | np.ndarray:
        """Return samples from the circuit.

        The circuit must define the detectors using DETECTOR instructions. Observables
        defined by OBSERVABLE_INCLUDE instructions can also be included in the results
        as honorary detectors.

        Args:
            shots: The number of times to sample every detector in the circuit.
            batch_size: The number of samples to process in each batch. When using TSIM
                and a GPU, it is recommended to increase this value until VRAM is fully
                utilized for maximum performance. For STIM, this argument is ignored.
            separate_observables: Defaults to False. When set to True, the return value
                is a (detection_events, observable_flips) tuple instead of a flat
                detection_events array.
                When sampling measurements, this argument is ignored.
            prepend_observables: Defaults to false. When set, observables are included
                with the detectors and are placed at the start of the results.
                When sampling measurements, this argument is ignored.
            append_observables: Defaults to false. When set, observables are included
                with the detectors and are placed at the end of the results.
                When sampling measurements, this argument is ignored.

        Returns:
            A numpy array or tuple of numpy arrays containing the samples.

        """
        kwargs = {}
        if self.sample_detectors:
            kwargs["prepend_observables"] = prepend_observables
            kwargs["append_observables"] = append_observables
            kwargs["separate_observables"] = separate_observables
        if self._supports_batch_size and batch_size is not None:
            kwargs["batch_size"] = batch_size
        return self.sampler.sample(shots=shots, **kwargs)

    def state(self) -> None:
        """Returns the state of the sampler."""
        raise NotImplementedError("State is not supported for STIM-type samplers.")


@dataclass
class SamplingSimulatorBase(
    AbstractSimulatorDevice["SamplingTaskBase"], Generic[TaskType]
):
    """Base class for STIM-based stabilizer circuit simulators.

    This class contains all the shared logic for compiling kernels to STIM
    and creating sampling tasks. Subclasses only need to set the _backend
    class variable to the appropriate module (stim or tsim).

    The compilation pipeline:
    1. Clone the kernel to avoid mutation
    2. Run SquinToStimPass to convert to STIM dialect
    3. Emit to STIM string format
    4. Create circuit using backend.Circuit()
    5. Compile sampler (measurement or detector)
    """

    _backend: ModuleType = field(init=False, repr=False)
    _task_class: type[TaskType] = field(init=False, repr=False)

    def task(
        self,
        kernel: ir.Method,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        *,
        sample_detectors: bool = False,
        seed: int | None = None,
    ) -> TaskType:
        """Compile the kernel and create a sampling task.

        Args:
            kernel: The kernel method to compile. Must have no arguments.
            args: Positional arguments. Will be ignored.
            kwargs: Keyword arguments. Will be ignored.
            sample_detectors: If True, compile a detector sampler.
                If False, compile a measurement sampler.
            seed: The seed for the random number generator.

        Returns:
            A SamplingTask.

        Raises:
            ValueError: If args or kwargs are provided.
        """
        if args or kwargs:
            raise ValueError("STIM sampling does not support kernel arguments")

        program_text = _codegen(kernel)
        circuit = self._backend.Circuit(program_text)

        if sample_detectors:
            sampler = circuit.compile_detector_sampler(seed=seed)
        else:
            sampler = circuit.compile_sampler(seed=seed)

        return self._task_class(
            kernel=kernel,
            args=(),
            kwargs={},
            sampler=sampler,
            program_text=program_text,
            sample_detectors=sample_detectors,
        )
