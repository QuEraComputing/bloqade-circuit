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

    ## Usage examples

    ```
    from bloqade import qasm2
    from bloqade.noise import native
    from bloqade.qasm2.passes.noise import NoisePass

    noise_main = qasm2.extended.add(native.dialect)

    @noise_main
    def main():
        q = qasm2.qreg(2)
        qasm2.h(q[0])
        qasm2.cx(q[0], q[1])
        return q

    # simple IR without any nosie
    main.print()

    noise_pass = NoisePass(noise_main)

    # rewrite stuff in-place
    noise_pass.unsafe_run(main)

    # now, we do have noise channels in the IR
    main.print()
    ```

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

    def unsafe_run(self, mt: ir.Method):
        result = LiftQubits(self.dialects).unsafe_run(mt)
        frame, _ = self.address_analysis.run_analysis(mt, no_raise=self.no_raise)
        result = (
            Walk(
                NoiseRewriteRule(
                    address_analysis=frame.entries,
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
