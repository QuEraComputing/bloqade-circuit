from typing import Sequence
from dataclasses import field, dataclass

from kirin import ir
from kirin.interp import InterpreterError
from kirin.analysis import ForwardExtra, const
from kirin.analysis.forward import ForwardFrame

from ..address import Address, AddressReg, ConstResult, AddressAnalysis



@dataclass
class FidelityFrame(ForwardFrame[Address]):
    gate_fidelities: list[list[float]] = field(init=False, default_factory=list)
    """Gate fidelities of each qubit as (min, max) pairs to provide a range"""

    qubit_survival_fidelities: list[list[float]] = field(init=False, default_factory=list)
    """Qubit survival fidelity given as (min, max) pairs"""

    parent_stmt: ir.Statement | None = None

    def extend_fidelity_lengths(self, n_qubits: int):
        """make sure there are at least n_qubits fidelity pairs"""

        self.gate_fidelities.extend([[1.0, 1.0] for _ in range(n_qubits - len(self.gate_fidelities))])
        self.qubit_survival_fidelities.extend([[1.0, 1.0] for _ in range(n_qubits - len(self.qubit_survival_fidelities))])

    def update_gate_fidelities(self, n_qubits: int, fidelity: float, addresses: AddressReg):
        """short-hand to update both (min, max) values"""

        self.extend_fidelity_lengths(n_qubits)

        print(n_qubits)
        print(self.gate_fidelities)

        for idx in addresses.data:
            self.gate_fidelities[idx][0] *= fidelity
            self.gate_fidelities[idx][1] *= fidelity

    def update_survival_fidelities(self, n_qubits: int, survival: float, addresses: AddressReg):
        """short-hand to update both (min, max) values"""

        self.extend_fidelity_lengths(n_qubits)

        for idx in addresses.data:
            self.qubit_survival_fidelities[idx][0] *= survival
            self.qubit_survival_fidelities[idx][1] *= survival


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

    gate_fidelity: float = 1.0
    """
    The fidelity of the gate set described by the analysed program. It reduces whenever a noise channel is encountered.
    """

    atom_survival_probability: list[float] = field(init=False)
    """
    The probabilities that each of the atoms in the register survive the duration of the analysed program. The order of the list follows the order they are in the register.
    """

    default_probabilities: dict[str, tuple[float, ...]] = field(default_factory=dict)
    """Default probabilities for noise statements where the probabilities are runtime values. The key must be equal to `stmt.name` and the number of values must match the probabilities.

    Example:

    ```python
    from bloqade import squin

    @squin.kernel
    def main():
        ...

    analysis = FidelityAnalysis(main.dialects, default_probabilities = {'single_qubit_pauli_channel': [1e-4, 1e-4, 1e-4]})
    ```
    """

    addr_frame: ForwardFrame[Address] | None = None
    addr_analysis: AddressAnalysis = field(init=False)


    # def initialize(self):
    #     super().initialize()
    #     self._current_gate_fidelity = 1.0
    #     self._current_atom_survival_probability = [
    #         1.0 for _ in range(len(self.atom_survival_probability))
    #     ]
    #     return self

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> FidelityFrame:
        frame = FidelityFrame(node, has_parent_access=has_parent_access)

        # if self.n_qubits is not None:
        #     frame.gate_fidelities = [[1.0, 1.0] for _ in range(self.n_qubits)]
        #     frame.qubit_survival_fidelities = [[1.0, 1.0] for _ in range(self.n_qubits)]

        return frame

    # def eval_fallback(self, frame: FidelityFrame, node: ir.Statement):
    #     # NOTE: default is to conserve fidelity, so do nothing here
    #     return tuple(self.lattice.bottom() for _ in range(len(node.results)))

    # def run(
    #     self, method: ir.Method, *args, **kwargs
    # ) -> tuple[FidelityFrame, Address]:
    #     self._run_address_analysis(method)

    #     assert self.n_qubits is not None

    #     return super().run(method, *args, **kwargs)

    # def _run_address_analysis(self, method: ir.Method):
    #     self.addr_analysis = AddressAnalysis(self.dialects)
    #     addr_frame, _ = self.addr_analysis.run(method=method)
    #     self.addr_frame = addr_frame

    #     # self.n_qubits = self.addr_analysis.qubit_count

    #     return addr_frame

        # NOTE: make sure we have as many probabilities as we have addresses
        # self.atom_survival_probability = [1.0] * addr_analysis.qubit_count

    def method_self(self, method: ir.Method) -> Address:
        return self.lattice.bottom()

    def _get_address(self, stmt: ir.Statement, key: ir.SSAValue):
        return self.state.current_frame.get(key)

    def get_address(self, frame: FidelityFrame, stmt: ir.Statement, key: ir.SSAValue):
        parent_stmt = frame.parent_stmt or stmt
        return self._get_address(parent_stmt, key)

    def get_addresses(
        self, frame: FidelityFrame, stmt: ir.Statement, keys: Sequence[ir.SSAValue]
    ):
        parent_stmt = frame.parent_stmt or stmt
        return tuple(self._get_address(parent_stmt, key) for key in keys)

    def get_const(self, frame: FidelityFrame, stmt: ir.Statement, key: ir.SSAValue):
        parent_stmt = frame.parent_stmt or stmt

        # NOTE: we rely on the address analysis to fetch constants and re-use the corresponding lattice element
        addr = self._get_address(parent_stmt, key)

        assert isinstance(addr, ConstResult)
        assert isinstance(result := addr.result, const.Value)

        return result.data
