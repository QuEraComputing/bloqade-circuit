from typing import Any, TypeVar, ParamSpec
from dataclasses import dataclass

from kirin import ir
from kirin.validation import ValidationSuite

from bloqade.device import AbstractRemoteDevice
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.gemini.analysis.logical_validation import GeminiLogicalValidation
from bloqade.gemini.analysis.measurement_validation import (
    GeminiTerminalMeasurementValidation,
)

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
        kwargs: dict[str, Any] = {},
        flatten: bool = True,
    ) -> GeminiLogicalTask:
        if flatten:
            AggressiveUnroll(kernel.dialects).fixpoint(kernel)

        # TODO: qubit number validation
        validator = ValidationSuite(
            [GeminiLogicalValidation, GeminiTerminalMeasurementValidation]
        )
        validation_result = validator.validate(kernel)
        validation_result.raise_if_invalid()

        return GeminiLogicalTask(kernel=kernel, args=args, kwargs=kwargs)
