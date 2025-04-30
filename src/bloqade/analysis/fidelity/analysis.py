from dataclasses import field

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward
from kirin.interp.value import Successor
from kirin.analysis.forward import ForwardFrame


class FidelityAnalysis(Forward):
    """
    This analysis pass can be used to track the global addresses of qubits and wires.
    """

    keys = ["circuit.fidelity"]
    lattice = EmptyLattice

    gate_fidelity: float = 1.0
    _current_gate_fidelity: float = field(init=False)

    atom_survival_probability: float = 1.0
    _current_atom_survival_probability: float = field(init=False)

    def initialize(self):
        super().initialize()
        self._current_gate_fidelity = 1.0
        self._current_atom_survival_probability = 1.0
        return self

    def posthook_succ(self, frame: ForwardFrame, succ: Successor):
        self.gate_fidelity *= self._current_gate_fidelity
        self.atom_survival_probability *= self._current_atom_survival_probability

    def eval_stmt_fallback(self, frame: ForwardFrame, stmt: ir.Statement):
        # NOTE: default is to conserve fidelity, so do nothing here
        return

    def run_method(self, method: ir.Method, args: tuple[EmptyLattice, ...]):
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)
