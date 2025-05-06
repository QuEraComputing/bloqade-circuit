from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Pass
from kirin.rewrite import (
    Walk,
    Fixpoint,
    DeadCodeElimination,
)

from bloqade.noise import native
from bloqade.analysis import address
from bloqade.qasm2.passes.lift_qubits import LiftQubits
from bloqade.qasm2.rewrite.heuristic_noise import NoiseRewriteRule


@dataclass
class NoisePass(Pass):
    """Apply a noise model to a quantum circuit.

    NOTE: This pass is not guaranteed to be supported long-term in bloqade. We will be
    moving towards a more general approach to noise modeling in the future.

    """

    noise_model: native.MoveNoiseModelABC = field(
        default_factory=native.TwoRowZoneModel
    )
    gate_noise_params: native.GateNoiseParams = field(
        default_factory=native.GateNoiseParams
    )
    address_analysis: address.AddressAnalysis = field(init=False)

    def __post_init__(self):
        self.address_analysis = address.AddressAnalysis(self.dialects)

    def get_qubit_values(self, mt: ir.Method):
        frame, _ = self.address_analysis.run_analysis(mt, no_raise=self.no_raise)
        qubit_ssa_values = {}
        # Traverse statements in block order to fine the first SSA value for each qubit
        for block in mt.callable_region.blocks:
            for stmt in block.stmts:
                if len(stmt.results) != 1:
                    continue

                addr = frame.entries.get(result := stmt.results[0])
                if (
                    isinstance(addr, address.AddressQubit)
                    and (index := addr.data) not in qubit_ssa_values
                ):
                    qubit_ssa_values[index] = result

        return qubit_ssa_values, frame.entries

    def unsafe_run(self, mt: ir.Method):
        result = LiftQubits(self.dialects).unsafe_run(mt)
        qubit_ssa_value, address_analysis = self.get_qubit_values(mt)
        result = (
            Walk(
                NoiseRewriteRule(
                    qubit_ssa_value=qubit_ssa_value,
                    address_analysis=address_analysis,
                    noise_model=self.noise_model,
                    gate_noise_params=self.gate_noise_params,
                ),
                reverse=True,
            )
            .rewrite(mt.code)
            .join(result)
        )

        result = Fixpoint(Walk(DeadCodeElimination())).rewrite(mt.code).join(result)
        return result
