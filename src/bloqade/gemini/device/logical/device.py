import warnings
from typing import Any, TypeVar, ParamSpec
from dataclasses import dataclass

from kirin import ir

from bloqade.device import AbstractRemoteDevice
from bloqade.validation import KernelValidation
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.gemini.analysis.logical_validation import GeminiLogicalValidationAnalysis

from .task import GeminiLogicalTask
from .mixins import GeminiAuthMixin

Param = ParamSpec("Param")
RetType = TypeVar("RetType")


@dataclass
class GeminiLogicalDevice(AbstractRemoteDevice[GeminiLogicalTask], GeminiAuthMixin):
    @property
    def num_qubits(self) -> int:
        return 10

    # TODO: fix method return type
    def task(
        self,
        kernel: ir.Method[Param, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        flatten: bool = True,
    ) -> GeminiLogicalTask:
        if args or kwargs:
            warnings.warn(
                "Gemini logical does not support any arguments, they will be ignored."
            )

        if flatten:
            AggressiveUnroll(kernel.dialects).fixpoint(kernel)

        # TODO: qubit number validation
        validation_pass = KernelValidation(GeminiLogicalValidationAnalysis)
        validation_pass.run(kernel)

        return GeminiLogicalTask(kernel=kernel, args=(), kwargs={})
