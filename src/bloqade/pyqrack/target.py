from typing import Any, TypeVar, Iterable
from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Fold

from bloqade.pyqrack.base import (
    StackMemory,
    DynamicMemory,
    PyQrackOptions,
    PyQrackInterpreter,
    _default_pyqrack_args,
)
from bloqade.analysis.address import AnyAddress, AddressAnalysis


@dataclass
class PyQrack:
    """PyQrack target runtime for Bloqade."""

    min_qubits: int = 0
    """Minimum number of qubits required for the PyQrack simulator.
    Useful when address analysis fails to determine the number of qubits.
    """
    dynamic_qubits: bool = False
    """Whether to use dynamic qubit allocation. Cannot use with tensor network simulations."""

    pyqrack_options: PyQrackOptions = field(default_factory=_default_pyqrack_args)
    """Options to pass to the QrackSimulator object, node `qubitCount` will be overwritten."""

    def __post_init__(self):
        self.pyqrack_options = PyQrackOptions(
            {**_default_pyqrack_args(), **self.pyqrack_options}
        )

    RetType = TypeVar("RetType")

    def _get_interp(self, mt: ir.Method[..., RetType]):
        if self.dynamic_qubits:

            options = self.pyqrack_options.copy()
            options["qubitCount"] = -1
            return PyQrackInterpreter(mt.dialects, memory=DynamicMemory(options))
        else:
            address_analysis = AddressAnalysis(mt.dialects)
            frame, _ = address_analysis.run_analysis(mt)
            if self.min_qubits == 0 and any(
                isinstance(a, AnyAddress) for a in frame.entries.values()
            ):
                raise ValueError(
                    "All addresses must be resolved. Or set min_qubits to a positive integer."
                )

            num_qubits = max(address_analysis.qubit_count, self.min_qubits)
            options = self.pyqrack_options.copy()
            options["qubitCount"] = num_qubits
            memory = StackMemory(
                options,
                total=num_qubits,
            )

            return PyQrackInterpreter(mt.dialects, memory=memory)

    def run(
        self,
        mt: ir.Method[..., RetType],
        *,
        shots: int = 1,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] = {},
        return_iterator: bool = False,
    ) -> RetType | list[RetType] | Iterable[RetType]:
        """Run the given kernel method on the PyQrack simulator.

        Args
            mt (Method):
                The kernel method to run.
            shots (int):
                The number of shots to run the simulation for.
                Defaults to 1.
            args (tuple[Any, ...]):
                Positional arguments to pass to the kernel method.
                Defaults to ().
            kwargs (dict[str, Any]):
                Keyword arguments to pass to the kernel method.
                Defaults to {}.
            return_iterator (bool):
                Whether to return an iterator that yields results for each shot.
                Defaults to False. if False, a list of results is returned.

        Returns
            RetType | list[RetType] | Iterable[RetType]:
                The result of the simulation. If `return_iterator` is True,
                an iterator that yields results for each shot is returned.
                Otherwise, a list of results is returned if `shots > 1`, or
                a single result is returned if `shots == 1`.

        """
        fold = Fold(mt.dialects)
        fold(mt)

        interpreter = self._get_interp(mt)

        def run_shots():
            for _ in range(shots):
                yield interpreter.run(mt, args, kwargs)

        if shots == 1:
            return interpreter.run(mt, args, kwargs)
        elif return_iterator:
            return run_shots()
        else:
            return list(run_shots())
