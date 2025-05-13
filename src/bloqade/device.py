import abc
from typing import Any, Generic, TypeVar, ParamSpec

from kirin import ir

from bloqade.task import (
    BatchFuture,
    AbstractTask,
    AbstractRemoteTask,
    AbstractSimulatorTask,
    DeviceTaskExpectMixin,
)

Params = ParamSpec("Params")
RetType = TypeVar("RetType")
ObsType = TypeVar("ObsType")


TaskType = TypeVar("TaskType", bound=AbstractTask)


class AbstractDevice(abc.ABC, Generic[TaskType]):
    """Abstract base class for devices. Defines the minimum interface for devices."""

    @abc.abstractmethod
    def task(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> TaskType:
        """Creates a remote task for the device."""


ExpectTaskType = TypeVar("ExpectTaskType", bound=DeviceTaskExpectMixin)


class ExpectationDeviceMixin(AbstractDevice[ExpectTaskType]):
    def expect(
        self,
        kernel: ir.Method[Params, RetType],
        observable: ir.Method[[RetType], ObsType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        *,
        shots: int = 1,
    ) -> ObsType:
        """Returns the expectation value of the given observable after running the task."""
        return self.task(kernel, args, kwargs).expect(observable, shots)


RemoteTaskType = TypeVar("RemoteTaskType", bound=AbstractRemoteTask)


class AbstractRemoteDevice(AbstractDevice[RemoteTaskType]):
    """Abstract base class for remote devices."""

    def run(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        *,
        shots: int = 1,
        timeout: float | None = None,
    ) -> list[RetType]:
        """Runs the kernel and returns the result.

        Args:
            kernel (ir.Method):
                The kernel method to run.
            args (tuple[Any, ...]):
                Positional arguments to pass to the kernel method.
            kwargs (dict[str, Any] | None):
                Keyword arguments to pass to the kernel method.
            shots (int):
                The number of times to run the kernel method.
            timeout (float | None):
                Timeout in seconds for the asynchronous execution. If None, wait indefinitely.

        Returns:
            list[RetType]:
                The result of the kernel method, if any.

        """
        return self.task(kernel, args, kwargs).run(shots=shots, timeout=timeout)

    def run_async(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        *,
        shots: int = 1,
    ) -> BatchFuture[RetType]:
        """Runs the kernel asynchronously and returns a Future object.

        Args:
            kernel (ir.Method):
                The kernel method to run.
            args (tuple[Any, ...]):
                Positional arguments to pass to the kernel method.
            kwargs (dict[str, Any] | None):
                Keyword arguments to pass to the kernel method.
            shots (int):
                The number of times to run the kernel method.

        Returns:
            Future[list[RetType]]:
                The Future for all executions of the kernel method.


        """
        return self.task(kernel, args, kwargs).run_async(shots=shots)


SimulatorTaskType = TypeVar("SimulatorTaskType", bound=AbstractSimulatorTask)


class AbstractSimulatorDevice(AbstractDevice[SimulatorTaskType]):
    """Abstract base class for simulator devices."""

    def run(
        self,
        kernel: ir.Method[Params, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> RetType:
        """Runs the kernel and returns the result."""
        return self.task(kernel, args, kwargs).run()
