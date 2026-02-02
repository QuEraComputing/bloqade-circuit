from dataclasses import dataclass

import cirq


@dataclass
class LossChannel(cirq.Gate):
    p: float

    def num_qubits(self) -> int:
        return 1


@dataclass
class CorrelatedLossChannel(cirq.Gate):
    p: float

    def num_qubits(self) -> int:
        return 2
