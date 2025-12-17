import json
import time
from typing import TypeVar, Sequence, ParamSpec
from warnings import warn
from dataclasses import dataclass

from qcs.common import (  # noqa: F401  NOTE: causes circular import issues if removed
    typing,
)
from kirin.serialization import JSONSerializer
from qcs.plugins.auth.api.client import AuthClient
from qcs.plugins.compilations.api import CompilationsClient
from qcs.plugins.tasks.api.client import TasksClient
from qcs.plugins.results.api.client import ResultsClient
from qcs.plugins.tasks.api.tasks_models import (
    Task,
    Program,
    Subtask,
    TaskStatus,
    TaskMetadata,
    TaskDefinition,
    TaskCreationRequest,
)

from bloqade import qasm2, squin
from bloqade.device import BatchFuture, AbstractRemoteTask

from .mixins import GeminiAuthMixin

Param = ParamSpec("Param")
RetType = TypeVar("RetType")


@dataclass
class GeminiLogicalFuture(BatchFuture[RetType], GeminiAuthMixin):
    task_id: str
    shots: int

    EXIT_STATUS = (
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
        TaskStatus.PAYLOAD_PROCESSING_ERROR,
        TaskStatus.COMPLETED,
    )

    def get_task(self) -> "Task":
        self.authenticate()
        with TasksClient(self.app_context) as client:
            return client.get(id=self.task_id)

    def get_compilation(self, compilation_id: str | None = None):
        self.authenticate()

        if compilation_id is None:
            compilation_id = self.get_task().compilation_id

        with CompilationsClient(self.app_context) as client:
            return client.get(id=compilation_id)

    def result(
        self, max_attempts: int | None = 10, delay: float = 0.1
    ) -> list[RetType]:
        max_iter = max_attempts or 0
        iter = 0
        status = self.status()
        while iter < max_iter:
            if status in self.EXIT_STATUS:
                break

            time.sleep(delay)
            iter += 1
            status = self.status()

        if status == TaskStatus.COMPLETED:
            with ResultsClient(self.app_context) as client:
                results = client.get(id=self.task_id)
            return self._postprocess_results(results)

        # NOTE: at this point we know something went wrong
        msg = f"Failed to fetch results of task with ID {self.task_id}. Reason: "

        if status not in self.EXIT_STATUS:
            raise TimeoutError(
                msg
                + f"Maximum attempts ({max_attempts}) reached. Current status is {status}"
            )

        if status == TaskStatus.CANCELLED:
            raise ValueError(msg + "the task was cancelled.")

        if status in (TaskStatus.FAILED, TaskStatus.PAYLOAD_PROCESSING_ERROR):
            task = self.get_task()
            raise ValueError(
                msg + f"the task failed with the errors {task.error_reasons}"
            )

        raise ValueError(f"Unexpected task status: {status}. Please report this issue.")

    def partial_result(self) -> Sequence[RetType | BatchFuture.MISSING_RESULT]:
        # let's just try to get what we can
        with ResultsClient(self.app_context) as client:
            try:
                results = client.get(id=self.task_id, raw_source=True)
            except Exception:
                return [None] * self.shots

        return self._postprocess_results(results)

    def _postprocess_results(
        self, results
    ) -> Sequence[RetType | BatchFuture.MISSING_RESULT]:
        retrieved_tasks = results.get("elements", [])
        if len(retrieved_tasks) == 0:
            return [None] * self.shots

        bitstrings = []
        for task in retrieved_tasks:
            subtasks = task.get("subtasks", [])

            if len(subtasks) == 0:
                return [None] * self.shots

            for subtask in subtasks:
                shot_results = subtask.get("shot_results", [])

                if len(shot_results) == 0:
                    bitstrings.append(None)
                    continue

                for shot_result in shot_results:
                    if not shot_result.get("frame_type", "").upper() == "SORTED":
                        continue

                    measurement = shot_result.get("measurement")
                    if measurement is None:
                        bitstrings.append(None)
                    else:
                        bitstrings.append(measurement.get("measurement_values"))

        return bitstrings

    def fetch(self) -> None:
        return super().fetch()

    def status(self):
        return self.get_task().task_status

    def cancel(self):
        """Attempts to cancel the execution of the future."""

        self.authenticate()
        with TasksClient(self.app_context) as client:
            try:
                return client.cancel(self.task_id)
            except Exception as e:
                warn(
                    f"Exception encountered when trying to cancel task with ID {self.task_id}: {str(repr(e))}"
                )

    def cancelled(self) -> bool:
        return self.status() == TaskStatus.CANCELLED


@dataclass
class GeminiLogicalTask(AbstractRemoteTask[Param, RetType], GeminiAuthMixin):
    task_definition_json: str | None = None
    program_language: str | None = None
    metadata: dict | None = None

    def __post_init__(self):
        if self.program_language is None:
            match self.kernel.dialects:
                case qasm2.main:
                    self.program_language = "qasm"
                case squin.kernel:
                    self.program_language = "squin"

            # TODO: better matching of language

    def authenticate(self):
        with AuthClient(self.app_context) as auth_client:
            if not auth_client.is_authenticated():
                return auth_client.login()

    def serialize_kernel(self) -> str:
        if self.kernel.dialects == qasm2.main:
            target = qasm2.emit.QASM2()
            qasm2_str = target.emit_str(self.kernel)
            return qasm2_str

        # TODO: better matching for programming language or different serialization for QASM2

        encoded_module = self.kernel.dialects.encode(self.kernel)
        return JSONSerializer().encode(encoded_module)

    def run_async(self, *, shots: int = 1) -> GeminiLogicalFuture:
        kernel_json = self.serialize_kernel()

        # Create program with metadata
        metadata = json.dumps(self.metadata) if self.metadata is None else None
        program = Program(
            content=kernel_json,
            program_metadata=TaskMetadata(
                user_metadata=metadata,
                system_metadata='{"sdk": "bloqad-circuit", "device": "gemini-logical"}',
            ),
        )

        # Create subtask to run the program `shots` times
        subtask = Subtask(
            program_index=0,
            num_shots=shots,
            arguments={},
            subtask_metadata=TaskMetadata(user_metadata=metadata),
        )

        # Create the task definition
        task_def = TaskDefinition(
            program_language=self.program_language,
            programs=[program],
            subtasks=[subtask],
        )

        # NOTE: store for later re-use
        self.task_definition_json = task_def.model_dump_json()

        # Authenticate
        self.authenticate()

        # Create task request
        task_request = TaskCreationRequest(root=task_def)

        # Submit using TasksClient with context manager
        with TasksClient(self.app_context) as tasks_client:
            tasks_client = TasksClient(self.app_context)
            created_task = tasks_client.create(body=task_request)

        if isinstance(created_task, Task):
            task_id = created_task.id
        else:
            # NOTE: JsonDict
            task_id = created_task.get("id")

        if not isinstance(task_id, str):
            raise ValueError(
                f"Couldn't get id of created task {created_task}. Please report this issue!"
            )

        return GeminiLogicalFuture(task_id, shots=shots)
