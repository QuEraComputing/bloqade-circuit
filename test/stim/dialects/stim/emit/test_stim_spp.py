import io
from bloqade import stim
from bloqade.stim.emit import EmitStimMain



def test_spp():

    @stim.main
    def test_spp_main():
        stim.spp(
            targets=(
                stim.pauli_string(
                    string=("X", "X", "Z"),
                    flipped=(True, False, False),
                    targets=(0, 1, 2),
                ),
                stim.pauli_string(
                    string=("Y", "X", "Y"),
                    flipped=(False, False, True),
                    targets=(3, 4, 5),
                ),
            ),
            dagger=False,
        )

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_spp_main)
    assert buf.getvalue().strip() == "SPP !X0*X1*Z2 Y3*X4*!Y5"

