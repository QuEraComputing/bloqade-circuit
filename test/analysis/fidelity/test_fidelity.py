import math

import pytest

from bloqade import qasm2
from bloqade.qasm2 import noise
from bloqade.analysis.fidelity import FidelityAnalysis
from bloqade.qasm2.passes.noise import NoisePass


def test_atom_loss_analysis():

    p_loss = 0.01

    @qasm2.extended
    def main():
        q = qasm2.qreg(2)
        noise.atom_loss_channel([q[0]], prob=p_loss)
        return q

    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run_analysis(main, no_raise=False)

    assert fid_analysis.gate_fidelity == fid_analysis._current_gate_fidelity == 1
    assert fid_analysis.atom_survival_probability[0] == 1 - p_loss
    assert fid_analysis.atom_survival_probability[1] == 1


def test_cz_noise():
    p_ch = 0.01 / 3.0

    @qasm2.extended
    def main():
        q = qasm2.qreg(2)
        noise.cz_pauli_channel(
            [q[0]],
            [q[1]],
            px_ctrl=p_ch,
            py_ctrl=p_ch,
            pz_ctrl=p_ch,
            px_qarg=p_ch,
            py_qarg=p_ch,
            pz_qarg=p_ch,
            paired=True,
        )
        qasm2.cz(q[0], q[1])
        return q

    main.print()

    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run_analysis(main, no_raise=False)

    expected_fidelity = (1 - 3 * p_ch) ** 2

    assert fid_analysis.gate_fidelity == fid_analysis._current_gate_fidelity
    assert math.isclose(fid_analysis.gate_fidelity, expected_fidelity)


def test_single_qubit_noise():
    p_ch = 0.01 / 3.0

    @qasm2.extended
    def main():
        q = qasm2.qreg(2)
        noise.pauli_channel([q[0]], px=p_ch, py=p_ch, pz=p_ch)
        return q

    main.print()

    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run_analysis(main, no_raise=False)

    expected_fidelity = 1 - 3 * p_ch

    assert fid_analysis.gate_fidelity == fid_analysis._current_gate_fidelity
    assert math.isclose(fid_analysis.gate_fidelity, expected_fidelity)


class NoiseTestModel(noise.MoveNoiseModelABC):
    def parallel_cz_errors(self, ctrls, qargs, rest):
        return {(0.01, 0.01, 0.01, 0.01): ctrls + qargs + rest}


@pytest.mark.xfail
def test_if():

    @qasm2.extended
    def main():
        q = qasm2.qreg(1)
        c = qasm2.creg(1)
        qasm2.h(q[0])
        qasm2.measure(q, c)
        qasm2.x(q[0])
        qasm2.measure(q, c)

        return c

    @qasm2.extended
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

    model = NoiseTestModel(
        global_loss_prob=p_loss,
        global_px=px,
        global_py=py,
        global_pz=pz,
        local_px=0.002,
    )
    NoisePass(main.dialects, noise_model=model)(main)
    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run_analysis(main, no_raise=False)

    model = NoiseTestModel()
    NoisePass(main_if.dialects, noise_model=model)(main_if)
    fid_if_analysis = FidelityAnalysis(main_if.dialects)
    fid_if_analysis.run_analysis(main_if, no_raise=False)

    assert 0 < fid_if_analysis.gate_fidelity == fid_analysis.gate_fidelity < 1
    assert (
        0
        < fid_if_analysis.atom_survival_probability[0]
        == fid_analysis.atom_survival_probability[0]
        < 1
    )


@pytest.mark.xfail
def test_for():

    @qasm2.extended
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

    @qasm2.extended
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

    model = NoiseTestModel(
        global_loss_prob=p_loss,
        global_px=px,
        global_py=py,
        global_pz=pz,
        local_px=0.002,
        local_loss_prob=0.03,
    )
    NoisePass(main.dialects, noise_model=model)(main)
    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run_analysis(main, no_raise=False)

    model = NoiseTestModel()
    NoisePass(main_for.dialects, noise_model=model)(main_for)

    main_for.print()

    fid_for_analysis = FidelityAnalysis(main_for.dialects)
    fid_for_analysis.run_analysis(main_for, no_raise=False)

    assert 0 < fid_for_analysis.gate_fidelity == fid_analysis.gate_fidelity < 1
    assert (
        0
        < fid_for_analysis.atom_survival_probability[0]
        == fid_analysis.atom_survival_probability[0]
        < 1
    )
