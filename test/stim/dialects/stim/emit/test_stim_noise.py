import io
from bloqade import stim
from bloqade.stim.emit import EmitStimMain



def test_noise():

    @stim.main
    def test_pauli2():
        stim.pauli_channel2(
            pix=0.1,
            piy=0.1,
            piz=0.1,
            pxi=0.1,
            pxx=0.1,
            pxy=0.1,
            pxz=0.1,
            pyi=0.1,
            pyx=0.1,
            pyy=0.1,
            pyz=0.1,
            pzi=0.1,
            pzx=0.1,
            pzy=0.1,
            pzz=0.1,
            targets=(0, 3, 4, 5),
        )


    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_pauli2)
    assert (buf.getvalue().strip() == "PAULI_CHANNEL_2(0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000, 0.10000000) 0 3 4 5"
    )


def test_qubit_loss():
    @stim.main
    def test_qubit_loss():
        stim.qubit_loss(probs=(0.1,), targets=(0, 1, 2))
    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_qubit_loss)
    assert buf.getvalue().strip() == "I_ERROR[loss](0.10000000) 0 1 2"


def test_correlated_qubit_loss():
    @stim.main
    def test_correlated_qubit_loss():
        stim.correlated_qubit_loss(probs=(0.1,), targets=(0, 1, 2), nonce=3)

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_correlated_qubit_loss)
    assert buf.getvalue().strip() == "I_ERROR[correlated_loss:3](0.10000000) 0 1 2"
