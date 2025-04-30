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

    # TODO: this should be a tuple[float, float] = (mean, max)
    current_fidelity: float = field(init=False)
    global_fidelity: float = 1.0
    # TODO: atom loss

    def initialize(self):
        super().initialize()
        self.current_fidelity = 1.0
        return self

    def posthook_succ(self, frame: ForwardFrame, succ: Successor):
        self.global_fidelity *= self.current_fidelity

    def eval_stmt_fallback(self, frame: ForwardFrame, stmt: ir.Statement):
        # print(
        #     "no implementation for stmt "
        #     + stmt.print_str(end="")
        #     + " from "
        #     + str(type(self))
        # )
        return

    def run_method(self, method: ir.Method, args: tuple[EmptyLattice, ...]):
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)
