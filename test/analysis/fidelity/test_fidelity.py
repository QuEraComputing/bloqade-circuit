import math

from kirin.dialects import ilist

from bloqade import qasm2, squin
from bloqade.qasm2 import noise
from bloqade.analysis.fidelity import FidelityRange, FidelityAnalysis
from bloqade.qasm2.passes.noise import NoisePass


def test_atom_loss_analysis():

    p_loss = 0.01

    @qasm2.extended
    def main():
        q = qasm2.qreg(2)
        noise.atom_loss_channel([q[0]], prob=p_loss)
        return q

    fid_analysis = FidelityAnalysis(main.dialects)
    fid_analysis.run(main)

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
    fid_analysis.run(main)

    expected_fidelity = (1 - 3 * p_ch) ** 2

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
    fid_analysis.run(main)

    expected_fidelity = 1 - 3 * p_ch

    assert math.isclose(fid_analysis.gate_fidelity, expected_fidelity)


class NoiseTestModel(noise.MoveNoiseModelABC):
    def parallel_cz_errors(self, ctrls, qargs, rest):
        return {(0.01, 0.01, 0.01, 0.01): ctrls + qargs + rest}


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
    fid_analysis.run(main)

    model = NoiseTestModel()
    NoisePass(main_if.dialects, noise_model=model)(main_if)
    fid_if_analysis = FidelityAnalysis(main_if.dialects)
    fid_if_analysis.run(main_if)

    assert 0 < fid_if_analysis.gate_fidelity == fid_analysis.gate_fidelity < 1
    assert (
        0
        < fid_if_analysis.atom_survival_probability[0]
        == fid_analysis.atom_survival_probability[0]
        < 1
    )


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
    fid_analysis.run(main)

    model = NoiseTestModel()
    NoisePass(main_for.dialects, noise_model=model)(main_for)

    main_for.print()

    fid_for_analysis = FidelityAnalysis(main_for.dialects)
    fid_for_analysis.run(main_for)

    assert 0 < fid_for_analysis.gate_fidelity == fid_analysis.gate_fidelity < 1
    assert (
        0
        < fid_for_analysis.atom_survival_probability[0]
        == fid_analysis.atom_survival_probability[0]
        < 1
    )


def test_stdlib_call():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.single_qubit_pauli_channel(0.1, 0.2, 0.3, q[0])
        squin.cx(q[0], q[1])
        squin.qubit_loss(0.1, q[1])

    fid_analysis = FidelityAnalysis(main.dialects)
    frame, _ = fid_analysis.run(main)

    print(fid_analysis.gate_fidelities)

    assert len(fid_analysis.gate_fidelities) == 2
    assert math.isclose(fid_analysis.gate_fidelities[0].max, 0.4)
    assert math.isclose(fid_analysis.gate_fidelities[0].min, 0.4)
    assert fid_analysis.gate_fidelities[1] == FidelityRange(1.0, 1.0)

    assert fid_analysis.qubit_survival_fidelities == [
        FidelityRange(1.0, 1.0),
        FidelityRange(0.9, 0.9),
    ]


def test_squin_if():

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        m = squin.measure(q[0])

        if m:
            qarg = [q[0]]
            squin.depolarize(0.1, qarg[0])
            squin.qubit_loss(0.25, q[1])
        else:
            squin.depolarize(0.2, q[1])
            squin.qubit_loss(0.15, q[0])

    fidelity_analysis = FidelityAnalysis(main.dialects)
    frame, _ = fidelity_analysis.run(main)

    assert fidelity_analysis.gate_fidelities == [
        FidelityRange(0.9, 1.0),
        FidelityRange(0.8, 1.0),
    ]
    assert fidelity_analysis.qubit_survival_fidelities == [
        FidelityRange(0.85, 1.0),
        FidelityRange(0.75, 1.0),
    ]


def test_squin_for():
    @squin.kernel
    def main():
        q = squin.qalloc(4)

        for i in range(4):
            squin.depolarize(0.01 * i, q[i])

    fidelity_analysis = FidelityAnalysis(main.dialects)
    frame, _ = fidelity_analysis.run(main)

    assert fidelity_analysis.gate_fidelities == [
        FidelityRange(1.0 - i * 0.01, 1.0 - i * 0.01) for i in range(4)
    ]


def test_all_noise_channels():
    @squin.kernel
    def main():
        q = squin.qalloc(6)
        squin.single_qubit_pauli_channel(0.15, 0.2, 0.25, q[0])
        squin.depolarize(0.2, q[1])
        squin.qubit_loss(0.1, q[0])

        squin.two_qubit_pauli_channel(
            ilist.IList(
                [
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                    0.01,
                ]
            ),
            q[2],
            q[3],
        )

        squin.depolarize2(0.15, q[4], q[5])

        squin.correlated_qubit_loss(0.13, ilist.IList([q[2], q[3], q[4], q[5]]))

    fidelity_analysis = FidelityAnalysis(main.dialects)
    frame, _ = fidelity_analysis.run(main)

    assert fidelity_analysis.gate_fidelities == [
        FidelityRange(
            0.4, 0.4
        ),  # squin.single_qubit_pauli_channel(0.15, 0.2, 0.25, q[0])
        FidelityRange(0.8, 0.8),  # squin.depolarize(0.2, q[1])
        FidelityRange(
            1 - 12 * 0.01, 1 - 12 * 0.01
        ),  # squin.two_qubit_pauli_channel(..., q[2])
        FidelityRange(
            1 - 12 * 0.01, 1 - 12 * 0.01
        ),  # squin.two_qubit_pauli_channel(..., q[3])
        FidelityRange(0.88, 0.88),  # squin.depolarize2(0.15, q[4])
        FidelityRange(0.88, 0.88),  # squin.depolarize2(0.15, q[5])
    ]

    assert (
        fidelity_analysis.qubit_survival_fidelities
        == [
            FidelityRange(0.9, 0.9),  # squin.qubit_loss(0.1, q[0])
            FidelityRange(1.0, 1.0),
        ]
        + [FidelityRange(0.87, 0.87)] * 4
    )  # squin.correlated_qubit_loss
