from dataclasses import field, dataclass

from ..address import AddressReg, AddressAnalysis


@dataclass
class FidelityRange:
    """Range of fidelity for a qubit as pair of (min, max) values"""

    min: float
    max: float


@dataclass
class FidelityAnalysis(AddressAnalysis):
    """
    This analysis pass can be used to track the global addresses of qubits and wires.

    ## Usage examples

    ```
    from bloqade import squin
    from bloqade.analysis.fidelity import FidelityAnalysis

    @squin.kernel
    def main():
        q = squin.qalloc(1)
        squin.x(q[0])
        squin.depolarize(0.1, q[0])
        return q

    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run(main)

    gate_fidelities = fid_analysis.gate_fidelities
    qubit_survival_probs = fid_analysis.qubit_survival_fidelities
    ```
    """

    keys = ("circuit.fidelity", "qubit.address")

    gate_fidelities: list[FidelityRange] = field(init=False, default_factory=list)
    """Gate fidelities of each qubit as (min, max) pairs to provide a range"""

    qubit_survival_fidelities: list[FidelityRange] = field(
        init=False, default_factory=list
    )
    """Qubit survival fidelity given as (min, max) pairs"""

    @property
    def next_address(self) -> int:
        return self._next_address

    @next_address.setter
    def next_address(self, value: int):
        # NOTE: hook into setter to make sure we always have fidelities of the correct length
        self._next_address = value
        self.extend_fidelities()

    def extend_fidelities(self):
        """Extend both fidelity lists so their length matches the number of qubits"""

        self.extend_fidelity(self.gate_fidelities)
        self.extend_fidelity(self.qubit_survival_fidelities)

    def extend_fidelity(self, fidelities: list[FidelityRange]):
        """Extend a list of fidelities so its length matches the number of qubits"""

        n = self.qubit_count
        fidelities.extend([FidelityRange(1.0, 1.0) for _ in range(n - len(fidelities))])

    def reset_fidelities(self):
        """Reset fidelities to unity for all qubits"""

        self.gate_fidelities = [
            FidelityRange(1.0, 1.0) for _ in range(self.qubit_count)
        ]
        self.qubit_survival_fidelities = [
            FidelityRange(1.0, 1.0) for _ in range(self.qubit_count)
        ]

    @staticmethod
    def update_fidelities(
        fidelities: list[FidelityRange], fidelity: float, addresses: AddressReg
    ):
        """short-hand to update both (min, max) values"""

        for idx in addresses.data:
            fidelities[idx].min *= fidelity
            fidelities[idx].max *= fidelity

    def update_branched_fidelities(
        self,
        fidelities: list[FidelityRange],
        current_fidelities: list[FidelityRange],
        then_fidelities: list[FidelityRange],
        else_fidelities: list[FidelityRange],
    ):
        """Update fidelity (min, max) values after evaluating differing branches such as IfElse"""
        # NOTE: make sure they are all of the same length
        map(
            self.extend_fidelity,
            (fidelities, current_fidelities, then_fidelities, else_fidelities),
        )

        # NOTE: now we update min / max accordingly
        for fid, current_fid, then_fid, else_fid in zip(
            fidelities, current_fidelities, then_fidelities, else_fidelities
        ):
            fid.min = current_fid.min * min(then_fid.min, else_fid.min)
            fid.max = current_fid.max * max(then_fid.max, else_fid.max)

    def initialize(self):
        super().initialize()
        self.reset_fidelities()
        return self
