from typing import Any
from dataclasses import field

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.interp.value import Successor
from kirin.analysis.forward import ForwardFrame

from ..address import AddressAnalysis


class FidelityAnalysis(Forward):
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

    _current_gate_fidelity: float = field(init=False)

    atom_survival_probability: list[float] = field(init=False)
    """
    The probabilities that each of the atoms in the register survive the duration of the analysed program. The order of the list follows the order they are in the register.
    """

    _current_atom_survival_probability: list[float] = field(init=False)

    addr_frame: ForwardFrame = field(init=False)

    def initialize(self):
        super().initialize()
        self._current_gate_fidelity = 1.0
        self._current_atom_survival_probability = [
            1.0 for _ in range(len(self.atom_survival_probability))
        ]
        return self

    def posthook_succ(self, frame: ForwardFrame, succ: Successor):
        self.gate_fidelity *= self._current_gate_fidelity
        for i, _current_survival in enumerate(self._current_atom_survival_probability):
            self.atom_survival_probability[i] *= _current_survival

    def eval_stmt_fallback(self, frame: ForwardFrame, stmt: ir.Statement):
        # NOTE: default is to conserve fidelity, so do nothing here
        return

    def run_method(self, method: ir.Method, args: tuple[EmptyLattice, ...]):
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    def run_analysis(
        self, method: ir.Method, args: tuple | None = None, *, no_raise: bool = True
    ) -> tuple[ForwardFrame, Any]:
        self._run_address_analysis(method, no_raise=no_raise)
        return super().run_analysis(method, args, no_raise=no_raise)

    def _run_address_analysis(self, method: ir.Method, no_raise: bool):
        addr_analysis = AddressAnalysis(self.dialects)
        addr_frame, _ = addr_analysis.run_analysis(method=method, no_raise=no_raise)
        self.addr_frame = addr_frame

        # NOTE: make sure we have as many probabilities as we have addresses
        self.atom_survival_probability = [1.0] * addr_analysis.qubit_count
