from dataclasses import field, dataclass

from kirin import ir
from kirin.analysis import const
from kirin.analysis.forward import ForwardFrame

from ..address import Address, AddressReg, ConstResult, AddressAnalysis


@dataclass
class FidelityAnalysis(AddressAnalysis):
    """
    This analysis pass can be used to track the global addresses of qubits and wires.

    ## Usage examples

    ```
    from bloqade import qasm2
    from bloqade.noise import native
    from bloqade.analysis.fidelity import FidelityAnalysis
    from bloqade.qasm2.passes.noise import NoisePass

    noise_main = qasm2.extended.add(native.dialect)

    @noise_main
    def main():
        q = qasm2.qreg(2)
        qasm2.x(q[0])
        return q

    NoisePass(main.dialects)(main)

    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run_analysis(main, no_raise=False)

    gate_fidelity = fid_analysis.gate_fidelity
    atom_survival_probs = fid_analysis.atom_survival_probability
    ```
    """

    keys = ("circuit.fidelity", "qubit.address")
    lattice = Address

    gate_fidelities: list[list[float]] = field(init=False, default_factory=list)
    """Gate fidelities of each qubit as (min, max) pairs to provide a range"""

    qubit_survival_fidelities: list[list[float]] = field(
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
        self.extend_fidelity(self.gate_fidelities)
        self.extend_fidelity(self.qubit_survival_fidelities)

    def extend_fidelity(self, fidelities: list[list[float]]):
        n = self.qubit_count
        fidelities.extend([[1.0, 1.0] for _ in range(n - len(fidelities))])

    def reset_fidelities(self):
        self.gate_fidelities = [[1.0, 1.0] for _ in range(self.qubit_count)]
        self.qubit_survival_fidelities = [[1.0, 1.0] for _ in range(self.qubit_count)]

    def update_gate_fidelities(self, fidelity: float, addresses: AddressReg):
        """short-hand to update both (min, max) values"""

        for idx in addresses.data:
            self.gate_fidelities[idx][0] *= fidelity
            self.gate_fidelities[idx][1] *= fidelity

    def update_survival_fidelities(self, survival: float, addresses: AddressReg):
        """short-hand to update both (min, max) values"""

        for idx in addresses.data:
            self.qubit_survival_fidelities[idx][0] *= survival
            self.qubit_survival_fidelities[idx][1] *= survival

    def update_branched_fidelities(
        self,
        fidelities: list[list[float]],
        current_fidelities: list[list[float]],
        then_fidelities: list[list[float]],
        else_fidelities: list[list[float]],
    ):
        # NOTE: make sure they are all of the same length
        map(
            self.extend_fidelity,
            (fidelities, current_fidelities, then_fidelities, else_fidelities),
        )

        # NOTE: now we update min / max accordingly
        for fid, current_fid, then_fid, else_fid in zip(
            fidelities, current_fidelities, then_fidelities, else_fidelities
        ):
            fid[0] = current_fid[0] * min(then_fid[0], else_fid[0])
            fid[1] = current_fid[1] * max(then_fid[1], else_fid[1])

    def initialize(self):
        super().initialize()
        self.gate_fidelities = []
        self.qubit_survival_fidelities = []
        return self

    def get_const(
        self, frame: ForwardFrame[Address], stmt: ir.Statement, key: ir.SSAValue
    ):
        addr = frame.get(key)
        assert isinstance(addr, ConstResult)
        assert isinstance(result := addr.result, const.Value)
        return result.data
