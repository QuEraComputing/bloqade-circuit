import re
from io import StringIO

from bloqade import stim
from bloqade.stim.emit import EmitStimMain

buf = StringIO()
interp = EmitStimMain(stim.main, io=buf)


def test_gates():
    @stim.main
    def test_single_qubit_gates():
        stim.sqrt_z(targets=(0, 1, 2), dagger=False)
        stim.x(targets=(0, 1, 2))
        stim.y(targets=(0, 1), dagger=True)
        stim.z(targets=(1, 2))
        stim.h(targets=(0, 1, 2), dagger=True)
        stim.s(targets=(0, 1, 2), dagger=False)
        stim.s(targets=(0, 1, 2), dagger=True)

    interp.run(test_single_qubit_gates)
    expected = """SQRT_Z 0 1 2
X 0 1 2
Y 0 1
Z 1 2
H 0 1 2
S 0 1 2
S_DAG 0 1 2"""
    assert buf.getvalue().strip() == expected

    @stim.main
    def test_two_qubit_gates():
        stim.swap(targets=(2, 3))

    interp.run(test_two_qubit_gates)
    expected = "SWAP 2 3"
    assert buf.getvalue().strip() == expected

    @stim.main
    def test_controlled_two_qubit_gates():
        stim.cx(controls=(0, 1), targets=(2, 3))
        stim.cy(controls=(0, 1), targets=(2, 3), dagger=True)
        stim.cz(controls=(0, 1), targets=(2, 3))

    interp.run(test_controlled_two_qubit_gates)
    expected = """CX 0 2 1 3
CY 0 2 1 3
CZ 0 2 1 3"""
    assert buf.getvalue().strip() == expected

    # @stim.main
    # def test_spp():
    #     pauli_string = stim.PauliString(string=('X', 'Y', 'Z'), targets=(0, 1, 2), flipped=(True, False, True))
    #     stim.spp(targets=(pauli_string, ), dagger=True)

    # interp.run(test_spp, args=())
    # print(interp.get_output())


def test_noise():
    @stim.main
    def test_depolarize():
        stim.depolarize1(p=0.1, targets=(0, 1, 2))
        stim.depolarize2(p=0.1, targets=(0, 1))

    interp.run(test_depolarize)
    expected = """DEPOLARIZE1(0.10000000) 0 1 2
DEPOLARIZE2(0.10000000) 0 1"""
    assert buf.getvalue().strip() == expected

    @stim.main
    def test_pauli_channel():
        stim.pauli_channel1(px=0.01, py=0.01, pz=0.1, targets=(0, 1, 2))
        stim.pauli_channel2(
            pix=0.01,
            piy=0.01,
            piz=0.1,
            pxi=0.01,
            pxx=0.01,
            pxy=0.01,
            pxz=0.1,
            pyi=0.01,
            pyx=0.01,
            pyy=0.01,
            pyz=0.1,
            pzi=0.1,
            pzx=0.1,
            pzy=0.1,
            pzz=0.2,
            targets=(0, 1, 2, 3),
        )

    interp.run(test_pauli_channel)
    expected = """PAULI_CHANNEL_1(0.01000000, 0.01000000, 0.10000000) 0 1 2
PAULI_CHANNEL_2(0.01000000, 0.01000000, 0.10000000, 0.01000000, 0.01000000, 0.01000000, 0.10000000, 0.01000000, 0.01000000, 0.01000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.20000000) 0 1 2 3"""
    assert buf.getvalue().strip() == expected

    @stim.main
    def test_pauli_error():
        stim.x_error(p=0.1, targets=(0, 1, 2))
        stim.y_error(p=0.1, targets=(0, 1))
        stim.z_error(p=0.1, targets=(1, 2))

    interp.run(test_pauli_error)
    expected = """X_ERROR(0.10000000) 0 1 2
Y_ERROR(0.10000000) 0 1
Z_ERROR(0.10000000) 1 2"""
    assert buf.getvalue().strip() == expected

    @stim.main
    def test_qubit_loss():
        stim.qubit_loss(probs=(0.1, 0.2), targets=(0, 1, 2))

    interp.run(test_qubit_loss)
    expected = "I_ERROR[loss](0.10000000, 0.20000000) 0 1 2"
    assert buf.getvalue().strip() == expected


def test_correlated_qubit_loss():

    @stim.main
    def test_correlated_qubit_loss():
        stim.correlated_qubit_loss(probs=(0.1,), targets=(0, 3, 1))

    interp.run(test_correlated_qubit_loss)
    assert re.match(
        r"I_ERROR\[correlated_loss:\d+\]\(0\.10000000\) 0 3 1", buf.getvalue().strip()
    )


def test_collapse():
    @stim.main
    def test_measure():
        stim.mx(p=0.0, targets=(0, 1, 2))
        stim.my(p=0.01, targets=(0, 1))
        stim.mz(p=0.02, targets=(1, 2))
        stim.mzz(p=0.03, targets=(0, 1, 2, 3))
        stim.myy(p=0.04, targets=(0, 1))
        stim.mxx(p=0.05, targets=(1, 2))

    interp.run(test_measure)
    expected = """MX(0.00000000) 0 1 2
MY(0.01000000) 0 1
MZ(0.02000000) 1 2
MZZ(0.03000000) 0 1 2 3
MYY(0.04000000) 0 1
MXX(0.05000000) 1 2"""
    assert buf.getvalue().strip() == expected

    @stim.main
    def test_reset():
        stim.rx(targets=(0, 1, 2))
        stim.ry(targets=(0, 1))
        stim.rz(targets=(1, 2))

    interp.run(test_reset)
    expected = """RX 0 1 2
RY 0 1
RZ 1 2"""
    assert buf.getvalue().strip() == expected


def test_repetition():
    @stim.main
    def test_repetition_memory():
        stim.rz(targets=(0, 1, 2, 3, 4))
        stim.tick()
        stim.depolarize1(p=0.1, targets=(0, 2, 4))
        stim.cx(controls=(0, 2), targets=(1, 3))
        stim.tick()
        stim.cx(controls=(2, 4), targets=(1, 3))
        stim.tick()
        stim.mz(p=0.1, targets=(1, 3))
        stim.detector(coord=(1, 0), targets=(stim.rec(-2),))
        stim.detector(coord=(3, 0), targets=(stim.rec(-1),))
        stim.rz(targets=(1, 3))
        stim.tick()
        stim.depolarize1(p=0.1, targets=(0, 2, 4))
        stim.cx(controls=(0, 2), targets=(1, 3))
        stim.tick()
        stim.cx(controls=(2, 4), targets=(1, 3))
        stim.tick()
        stim.mz(p=0.1, targets=(1, 3))
        stim.detector(coord=(1, 1), targets=(stim.rec(-2), stim.rec(-4)))
        stim.detector(coord=(3, 1), targets=(stim.rec(-1), stim.rec(-3)))
        stim.mz(p=0.1, targets=(0, 2, 4))
        stim.detector(coord=(1, 2), targets=(stim.rec(-2), stim.rec(-3), stim.rec(-5)))
        stim.detector(coord=(3, 2), targets=(stim.rec(-1), stim.rec(-2), stim.rec(-4)))
        stim.observable_include(idx=0, targets=(stim.rec(-1),))

    interp.run(test_repetition_memory)
    expected = """RZ 0 1 2 3 4
TICK
DEPOLARIZE1(0.10000000) 0 2 4
CX 0 1 2 3
TICK
CX 2 1 4 3
TICK
MZ(0.10000000) 1 3
DETECTOR(1, 0) rec[-2]
DETECTOR(3, 0) rec[-1]
RZ 1 3
TICK
DEPOLARIZE1(0.10000000) 0 2 4
CX 0 1 2 3
TICK
CX 2 1 4 3
TICK
MZ(0.10000000) 1 3
DETECTOR(1, 1) rec[-2] rec[-4]
DETECTOR(3, 1) rec[-1] rec[-3]
MZ(0.10000000) 0 2 4
DETECTOR(1, 2) rec[-2] rec[-3] rec[-5]
DETECTOR(3, 2) rec[-1] rec[-2] rec[-4]
OBSERVABLE_INCLUDE(0) rec[-1]"""
    assert buf.getvalue().strip() == expected
