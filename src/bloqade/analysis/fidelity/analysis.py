from typing import Sequence
from dataclasses import field, dataclass

from kirin import ir
from kirin.interp import InterpreterError
from kirin.lattice import EmptyLattice
from kirin.analysis import ForwardExtra, const
from kirin.analysis.forward import ForwardFrame

from ..address import Address, AddressReg, ConstResult, AddressAnalysis


def init_nested_dict():
    return dict(dict())


@dataclass
class FidelityFrame(ForwardFrame[EmptyLattice]):
    gate_fidelities: list[list[float]] = field(init=False)
    """Gate fidelities of each qubit as (min, max) pairs to provide a range"""

    parent_stmt: ir.Statement | None = None

    def update_fidelities(self, fidelity: float, addresses: AddressReg):
        """short-hand to update both (min, max) values"""

        for idx in addresses.data:
            self.gate_fidelities[idx][0] *= fidelity
            self.gate_fidelities[idx][1] *= fidelity


@dataclass
class FidelityAnalysis(ForwardExtra[FidelityFrame, EmptyLattice]):
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

    keys = ["circuit.fidelity"]
    lattice = EmptyLattice

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

    collected_addresses: dict[ir.Statement, dict[ir.SSAValue, Address]] = field(
        default_factory=init_nested_dict
    )

    n_qubits: int | None = None

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

        if self.n_qubits is not None:
            frame.gate_fidelities = [[1.0, 1.0] for _ in range(self.n_qubits)]

        return frame

    def eval_fallback(self, frame: FidelityFrame, node: ir.Statement):
        # NOTE: default is to conserve fidelity, so do nothing here
        return tuple(self.lattice.bottom() for _ in range(len(node.results)))

    def run(
        self, method: ir.Method, *args, **kwargs
    ) -> tuple[FidelityFrame, EmptyLattice]:
        self._run_address_analysis(method)

        assert self.n_qubits is not None

        return super().run(method, *args, **kwargs)

    def _run_address_analysis(self, method: ir.Method):
        self.addr_analysis = AddressAnalysis(self.dialects)
        addr_frame, _ = self.addr_analysis.run(method=method)
        self.addr_frame = addr_frame

        self.n_qubits = self.addr_analysis.qubit_count

        return addr_frame

        # NOTE: make sure we have as many probabilities as we have addresses
        # self.atom_survival_probability = [1.0] * addr_analysis.qubit_count

    def method_self(self, method: ir.Method) -> EmptyLattice:
        return self.lattice.bottom()

    def _get_address(self, stmt: ir.Statement, key: ir.SSAValue):
        addr = None

        if self.addr_frame is not None:
            addr = self.addr_frame.entries.get(key)

        if addr is not None:
            return addr

        collected_addr = self.collected_addresses.get(stmt)
        if collected_addr is not None:
            addr = collected_addr.get(key)

        if addr is None:
            raise InterpreterError(f"Address of {key} at statement {stmt} not found!")

        return addr

    def get_address(self, frame: FidelityFrame, stmt: ir.Statement, key: ir.SSAValue):
        parent_stmt = frame.parent_stmt or stmt
        return self._get_address(parent_stmt, key)

    def get_addresses(
        self, frame: FidelityFrame, stmt: ir.Statement, keys: Sequence[ir.SSAValue]
    ):
        parent_stmt = frame.parent_stmt or stmt
        return tuple(self._get_address(parent_stmt, key) for key in keys)

    def store_addresses(
        self,
        frame: FidelityFrame,
        stmt: ir.Statement,
        addresses: dict[ir.SSAValue, Address],
    ):
        parent_stmt = frame.parent_stmt or stmt
        self._store_addresses(parent_stmt, addresses)

    def _store_addresses(
        self, stmt: ir.Statement, addresses: dict[ir.SSAValue, Address]
    ):
        if stmt in self.collected_addresses:
            self.collected_addresses[stmt].update(addresses)
        else:
            self.collected_addresses[stmt] = addresses

    def get_const(self, frame: FidelityFrame, stmt: ir.Statement, key: ir.SSAValue):
        parent_stmt = frame.parent_stmt or stmt

        # NOTE: we rely on the address analysis to fetch constants and re-use the corresponding lattice element
        addr = self._get_address(parent_stmt, key)

        assert isinstance(addr, ConstResult)
        assert isinstance(result := addr.result, const.Value)

        return result.data
