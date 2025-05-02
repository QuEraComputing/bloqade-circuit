import abc
from typing import Any, Generic, TypeVar, ParamSpec

from kirin import ir

from bloqade.task import Future, RemoteTask, AbstractTask, SimulatorTask

TaskType = TypeVar("TaskType", bound=AbstractTask)
Params = ParamSpec("Params")
RetType = TypeVar("RetType")
ObsType = TypeVar("ObsType")


class AbstractDevice(abc.ABC, Generic[TaskType]):
    """Abstract base class for devices."""


RemoteTaskType = TypeVar("RemoteTaskType", bound=RemoteTask)


class AbstractRemoteDevice(AbstractDevice[RemoteTaskType]):
    """Abstract base class for remote devices."""

    @abc.abstractmethod
    def task(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> RemoteTaskType:
        """Creates a remote task for the device."""

    def run(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        shots: int = 1,
        timeout: float | None = None,
    ) -> RetType:
        """Runs the kernel and returns the result."""
        return self.task(kernel, args, kwargs).run(shots=shots, timeout=timeout)

    def run_async(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        shots: int = 1,
    ) -> Future[RetType]:
        """Runs the kernel asynchronously and returns a Future object."""
        return self.task(kernel, args, kwargs).run_async(shots=shots)

    def expect(
        self,
        kernel: ir.Method[Params, RetType],
        observable: ir.Method[[RetType], ObsType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        shots: int = 1,
    ) -> ObsType:
        """Returns the expectation value of the given observable after running the task."""
        return self.task(kernel, args, kwargs).expect(observable, shots=shots)


SimulatorTaskType = TypeVar("SimulatorTaskType", bound=SimulatorTask)


class AbstractSimulatorDevice(AbstractDevice[SimulatorTaskType]):
    """Abstract base class for simulator devices."""

    @abc.abstractmethod
    def task(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> SimulatorTaskType:
        """Creates a simulator task for the device."""

    def run(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> RetType:
        """Runs the kernel and returns the result."""
        return self.task(kernel, args, kwargs).run()

    def rdm(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        """Runs the kernel and returns the reduced density matrix."""
        return self.task(kernel, args, kwargs).rdm()

    def expect(
        self,
        kernel: ir.Method[Params, RetType],
        observable: ir.Method[[RetType], ObsType],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> ObsType:
        """Returns the expectation value of the given observable after running the task."""
        return self.task(kernel, args, kwargs).expect(observable)
