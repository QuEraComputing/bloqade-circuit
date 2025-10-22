import io
from bloqade import stim
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.parse import loads
from bloqade.stim.dialects import noise

emit = EmitStimMain()


def codegen(mt):
    # method should not have any arguments!
    emit.initialize()
    emit.run(mt=mt, args=())
    return emit.get_output()


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
        stim.correlated_qubit_loss(probs=(0.1,), targets=(0, 1, 2))

    out = codegen(test_correlated_qubit_loss)
    assert out.strip() == "I_ERROR[correlated_loss:0](0.10000000) 0 1 2"


def test_correlated_qubit_loss_multiple():

    @stim.main
    def test_correlated_qubit_loss_multiple():
        stim.correlated_qubit_loss(probs=(0.1,), targets=(0, 1))
        stim.correlated_qubit_loss(probs=(0.1,), targets=(2, 3))

    for i in range(2):  # repeat the test to ensure the identifier is reset each time
        out = codegen(test_correlated_qubit_loss_multiple).strip()
        print(out)
        assert (
            out.strip()
            == "I_ERROR[correlated_loss:0](0.10000000) 0 1\n"
            + "I_ERROR[correlated_loss:1](0.10000000) 2 3"
        )


def test_correlated_qubit_codegen_roundtrip():
    @stim.main
    def test():
        stim.correlated_qubit_loss(probs=(0.1,), targets=(0, 1, 2))
        stim.qubit_loss(probs=(0.2,), targets=(2,))
        stim.correlated_qubit_loss(probs=(0.3,), targets=(3, 4))

    stim_str = codegen(test)

    mt = loads(
        stim_str,
        nonstim_noise_ops={
            "loss": noise.QubitLoss,
            "correlated_loss": noise.CorrelatedQubitLoss,
        },
    )
    assert codegen(mt) == stim_str
