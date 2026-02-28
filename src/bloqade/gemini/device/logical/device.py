import warnings
from typing import Any, TypeVar, Callable, Iterator, ParamSpec, cast
from dataclasses import dataclass

import numpy as np
from kirin import ir
from kirin.validation import ValidationSuite

from bloqade.device import AbstractRemoteDevice
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.analysis.address import AddressAnalysis
from bloqade.gemini.analysis.logical_validation import GeminiLogicalValidation
from bloqade.analysis.validation.simple_nocloning import FlatKernelNoCloningValidation
from bloqade.gemini.analysis.measurement_validation import (
    GeminiTerminalMeasurementValidation,
)
from bloqade.gemini.logical.dialects.operations.stmts import TerminalLogicalMeasurement
from bloqade.gemini.logical.rewrite.remove_postprocessing import RemovePostProcessing

from .task import GeminiLogicalTask
from ...post_processing import generate_post_processing

Param = ParamSpec("Param")
RetType = TypeVar("RetType")


@dataclass
class GeminiLogicalDevice(AbstractRemoteDevice[GeminiLogicalTask]):
    @property
    def max_qubits(self) -> int:
        return 10

    def task(
        self,
        kernel: ir.Method[Param, RetType],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] = {},
        flatten: bool = True,
    ) -> GeminiLogicalTask:
        if flatten:
            AggressiveUnroll(kernel.dialects).fixpoint(kernel)

        address_analysis = AddressAnalysis(kernel.dialects)
        address_analysis.run(kernel, *args, **kwargs)
        used_qubits = address_analysis.qubit_count

        if used_qubits > self.max_qubits:
            raise ValueError(
                f"Submitted kernel uses {used_qubits} qubits, but only {self.max_qubits} are supported in logical mode."
            )

        # TODO: we could re-use the address analysis run above for this
        validator = ValidationSuite(
            passes=[
                GeminiLogicalValidation,
                GeminiTerminalMeasurementValidation,
                FlatKernelNoCloningValidation,
            ]
        )
        validation_result = validator.validate(kernel)
        validation_result.raise_if_invalid()

        execution_kernel, postprocessing_function = (
            self.split_execution_from_postprocessing(kernel)
        )

        num_physical_qubits = self.extract_physical_qubits(execution_kernel)

        if num_physical_qubits is None:
            raise ValueError(
                "Failed to determine the number of physical qubits per logical qubit."
            )

        return GeminiLogicalTask(
            kernel,
            args,
            kwargs,
            execution_kernel=execution_kernel,
            postprocessing_function=postprocessing_function,
            n_qubits=used_qubits,
            num_physical_qubits=num_physical_qubits,
        )

    def split_execution_from_postprocessing(
        self, kernel: ir.Method[Param, RetType]
    ) -> tuple[
        ir.Method[Param, None], Callable[[np.ndarray], Iterator[RetType]] | None
    ]:
        postprocessing_function = generate_post_processing(kernel)

        if postprocessing_function is None:
            warnings.warn("Failed to generate post-processing function")

        kernel_ = kernel.similar()
        RemovePostProcessing(kernel_.dialects)(kernel_)

        return cast(ir.Method[Param, None], kernel_), postprocessing_function

    def extract_physical_qubits(self, kernel: ir.Method) -> int | None:
        for stmt in kernel.callable_region.stmts():
            if isinstance(stmt, TerminalLogicalMeasurement):
                return stmt.num_physical_qubits
