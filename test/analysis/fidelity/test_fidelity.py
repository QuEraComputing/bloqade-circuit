from bloqade import qasm2
from bloqade.noise import native
from bloqade.analysis.fidelity import FidelityAnalysis
from bloqade.qasm2.passes.noise import NoisePass

noise_main = qasm2.extended.add(native.dialect)


class NoiseTestModel(native.MoveNoiseModelABC):
    def parallel_cz_errors(self, ctrls, qargs, rest):
        return {(0.01, 0.01, 0.01, 0.01): ctrls + qargs + rest}


def test_basic_noise():

    @noise_main
    def main():
        q = qasm2.qreg(2)
        qasm2.x(q[0])
        return q

    main.print()

    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run_analysis(main, no_raise=False)

    assert fid_analysis.gate_fidelity == fid_analysis._current_gate_fidelity == 1

    px = 0.01
    py = 0.01
    pz = 0.01
    p_loss = 0.01

    noise_params = native.GateNoiseParams(
        global_loss_prob=p_loss,
        global_px=px,
        global_py=py,
        global_pz=pz,
        local_px=0.002,
    )

    model = NoiseTestModel()

    NoisePass(main.dialects, noise_model=model, gate_noise_params=noise_params)(main)

    main.print()

    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run_analysis(main, no_raise=False)

    p_noise = noise_params.local_px + noise_params.local_py + noise_params.local_pz
    assert (
        fid_analysis.gate_fidelity
        == fid_analysis._current_gate_fidelity
        == (1 - p_noise)
    )

    assert 0.9 < fid_analysis.atom_survival_probability < 1
    assert fid_analysis.atom_survival_probability == 1 - noise_params.local_loss_prob


def test_if():

    @noise_main
    def main():
        q = qasm2.qreg(1)
        c = qasm2.creg(1)
        qasm2.h(q[0])
        qasm2.measure(q, c)
        qasm2.x(q[0])
        qasm2.measure(q, c)

        return c

    @noise_main
    def main_if():
        q = qasm2.qreg(1)
        c = qasm2.creg(1)
        qasm2.h(q[0])
        qasm2.measure(q, c)

        if c[0] == 0:
            qasm2.x(q[0])

        qasm2.measure(q, c)
        return c

    px = 0.01
    py = 0.01
    pz = 0.01
    p_loss = 0.01

    noise_params = native.GateNoiseParams(
        global_loss_prob=p_loss,
        global_px=px,
        global_py=py,
        global_pz=pz,
        local_px=0.002,
    )

    model = NoiseTestModel()
    NoisePass(main.dialects, noise_model=model, gate_noise_params=noise_params)(main)
    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run_analysis(main, no_raise=False)

    model = NoiseTestModel()
    NoisePass(main_if.dialects, noise_model=model, gate_noise_params=noise_params)(
        main_if
    )
    fid_if_analysis = FidelityAnalysis(main_if.dialects)
    fid_if_analysis.run_analysis(main_if, no_raise=False)

    assert 0 < fid_if_analysis.gate_fidelity == fid_analysis.gate_fidelity < 1
    assert (
        0
        < fid_if_analysis.atom_survival_probability
        == fid_analysis.atom_survival_probability
        < 1
    )


def test_for():

    @noise_main
    def main():
        q = qasm2.qreg(1)
        c = qasm2.creg(1)
        qasm2.h(q[0])
        qasm2.measure(q, c)

        # unrolled for loop
        qasm2.x(q[0])
        qasm2.x(q[0])
        qasm2.x(q[0])

        qasm2.measure(q, c)

        return c

    @noise_main
    def main_for():
        q = qasm2.qreg(1)
        c = qasm2.creg(1)
        qasm2.h(q[0])
        qasm2.measure(q, c)

        for _ in range(3):
            qasm2.x(q[0])

        qasm2.measure(q, c)
        return c

    px = 0.01
    py = 0.01
    pz = 0.01
    p_loss = 0.01

    noise_params = native.GateNoiseParams(
        global_loss_prob=p_loss,
        global_px=px,
        global_py=py,
        global_pz=pz,
        local_px=0.002,
        local_loss_prob=0.03,
    )

    model = NoiseTestModel()
    NoisePass(main.dialects, noise_model=model, gate_noise_params=noise_params)(main)
    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run_analysis(main, no_raise=False)

    model = NoiseTestModel()
    NoisePass(main_for.dialects, noise_model=model, gate_noise_params=noise_params)(
        main_for
    )

    main_for.print()

    fid_for_analysis = FidelityAnalysis(main_for.dialects)
    fid_for_analysis.run_analysis(main_for, no_raise=False)

    assert 0 < fid_for_analysis.gate_fidelity == fid_analysis.gate_fidelity < 1
    assert (
        0
        < fid_for_analysis.atom_survival_probability
        == fid_analysis.atom_survival_probability
        < 1
    )
