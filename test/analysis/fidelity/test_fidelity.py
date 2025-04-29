from bloqade import qasm2
from bloqade.noise import native
from bloqade.analysis.fidelity import FidelityAnalysis
from bloqade.qasm2.passes.noise import NoisePass

noise_main = qasm2.extended.add(native.dialect)


class NoiseTestModel(native.MoveNoiseModelABC):
    def parallel_cz_errors(self, ctrls, qargs, rest):
        return {(0.01, 0.01, 0.01, 0.01): ctrls + qargs + rest}


@noise_main
def main():
    q = qasm2.qreg(2)
    qasm2.x(q[0])
    return q


main.print()

fid_analysis = FidelityAnalysis(main.dialects)
fid_analysis.run_analysis(main)

assert fid_analysis.global_fidelity == fid_analysis.current_fidelity == 1


px = 0.01
py = 0.01
pz = 0.01
p_loss = 0.01

noise_params = native.GateNoiseParams(
    global_loss_prob=p_loss, global_px=px, global_py=py, global_pz=pz
)

model = NoiseTestModel()


NoisePass(main.dialects, noise_model=model, gate_noise_params=noise_params)(main)


main.print()

fid_analysis = FidelityAnalysis(main.dialects)
fid_analysis.run_analysis(main, no_raise=False)

print(fid_analysis.global_fidelity)
print(fid_analysis.current_fidelity)
