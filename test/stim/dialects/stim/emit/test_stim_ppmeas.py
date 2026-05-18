import io

from bloqade import stim
from bloqade.stim.emit import EmitStimMain


def test_mpp():

    @stim.main
    def test_mpp_main():
        stim.mpp(
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
            p=0.3,
        )

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_mpp_main)
    assert buf.getvalue().strip() == "MPP(0.30000000) !X0*X1*Z2 Y3*X4*!Y5"
