from typing import List, TypeVar, ParamSpec
from warnings import warn
from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Fold

from bloqade.qrb.base import (
    StackMemory,
    DynamicMemory,
    QRBOptions,
    QRBInterpreter,
    _default_qrb_args,
)
from bloqade.analysis.address import UnknownQubit, AddressAnalysis

Params = ParamSpec("Params")
RetType = TypeVar("RetType")


@dataclass
class QRB:
    """qrackbind target runtime for Bloqade."""

    min_qubits: int = 0
    """Minimum number of qubits required for the qrackbind simulator.
    Useful when address analysis fails to determine the number of qubits.
    """
    dynamic_qubits: bool = False
    """Whether to use dynamic qubit allocation. Cannot use with tensor network simulations."""

    qrb_options: QRBOptions = field(default_factory=_default_qrb_args)
    """Options to pass to the QrackSimulator object; note `qubitCount` will be overwritten."""

    def __post_init__(self):
        warn(
            "The QRB target is deprecated and will be removed "
            "in a future release. Please use the DynamicMemorySimulator / "
            "StackMemorySimulator instead."
        )

        self.qrb_options = QRBOptions(
            {**_default_qrb_args(), **self.qrb_options}
        )

    def _get_interp(self, mt: ir.Method[Params, RetType]):
        if self.dynamic_qubits:
            options = self.qrb_options.copy()
            options["qubitCount"] = -1
            return QRBInterpreter(mt.dialects, memory=DynamicMemory(options))
        else:
            address_analysis = AddressAnalysis(mt.dialects)
            frame, _ = address_analysis.run(mt)
            if self.min_qubits == 0 and any(
                isinstance(a, UnknownQubit) for a in frame.entries.values()
            ):
                raise ValueError(
                    "All addresses must be resolved. Or set min_qubits to a positive integer."
                )

            num_qubits = max(address_analysis.qubit_count, self.min_qubits)
            options = self.qrb_options.copy()
            options["qubitCount"] = num_qubits
            memory = StackMemory(options, total=num_qubits)
            return QRBInterpreter(mt.dialects, memory=memory)

    def run(
        self,
        mt: ir.Method[Params, RetType],
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> RetType:
        """Run the given kernel method on the qrackbind simulator.

        Args
            mt (Method):
                The kernel method to run.

        Returns
            The result of the kernel method, if any.

        """
        fold = Fold(mt.dialects)
        fold(mt)
        _, ret = self._get_interp(mt).run(mt, *args, **kwargs)
        return ret

    def multi_run(
        self,
        mt: ir.Method[Params, RetType],
        _shots: int,
        *args: Params.args,
        **kwargs: Params.kwargs,
    ) -> List[RetType]:
        """Run the given kernel method on the qrackbind simulator `_shots` times.

        Args
            mt (Method):
                The kernel method to run.
            _shots (int):
                The number of times to run the kernel method.

        Returns
            List of results of the kernel method, one for each shot.

        """
        fold = Fold(mt.dialects)
        fold(mt)

        interpreter = self._get_interp(mt)
        batched_results = []
        for _ in range(_shots):
            batched_results.append(interpreter.run(mt, args, kwargs))

        return batched_results
