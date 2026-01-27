import io

from bloqade import stim
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.dialects import gate


def test_single_qubit_gate_with_tag():
    """Test single qubit gates with tag annotation."""

    @stim.main
    def test_x_with_tag():
        stim.x(targets=(0, 1), tag="my_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_x_with_tag)
    assert buf.getvalue().strip() == "X[my_tag] 0 1"


def test_single_qubit_gate_without_tag():
    """Test single qubit gates without tag (backward compatibility)."""

    @stim.main
    def test_x_no_tag():
        stim.x(targets=(0, 1))

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_x_no_tag)
    assert buf.getvalue().strip() == "X 0 1"


def test_s_gate_with_tag():
    """Test S gate with tag, including dagger variant."""

    @stim.main
    def test_s_with_tag():
        stim.s(targets=(0,), tag="s_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_s_with_tag)
    assert buf.getvalue().strip() == "S[s_tag] 0"

    @stim.main
    def test_s_dag_with_tag():
        stim.s(targets=(0,), dagger=True, tag="s_dag_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_s_dag_with_tag)
    assert buf.getvalue().strip() == "S_DAG[s_dag_tag] 0"


def test_controlled_gate_with_tag():
    """Test controlled two-qubit gates with tag annotation."""

    @stim.main
    def test_cx_with_tag():
        gate.CX(controls=(0,), targets=(1,), tag="cx_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_cx_with_tag)
    assert buf.getvalue().strip() == "CX[cx_tag] 0 1"


def test_swap_gate_with_tag():
    """Test SWAP gate with tag annotation."""

    @stim.main
    def test_swap_with_tag():
        stim.swap(targets=(0, 1), tag="swap_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_swap_with_tag)
    assert buf.getvalue().strip() == "SWAP[swap_tag] 0 1"


def test_t_gate_with_tag():
    """Test T gate with tag annotation."""

    @stim.main
    def test_t_with_tag():
        stim.t(targets=(0,), tag="t_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_t_with_tag)
    assert buf.getvalue().strip() == "S[T][t_tag] 0"

    @stim.main
    def test_t_dag_with_tag():
        stim.t(targets=(0,), dagger=True, tag="t_dag_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_t_dag_with_tag)
    assert buf.getvalue().strip() == "S_DAG[T][t_dag_tag] 0"


def test_spp_with_tag():
    """Test SPP gate with tag annotation."""

    @stim.main
    def test_spp_with_tag():
        stim.spp(
            targets=(
                stim.pauli_string(
                    string=("X", "Z"),
                    flipped=(False, False),
                    targets=(0, 1),
                ),
            ),
            tag="spp_tag",
        )

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_spp_with_tag)
    assert buf.getvalue().strip() == "SPP[spp_tag] X0*Z1"


def test_rotation_gate_with_tag():
    """Test rotation gates (Rx, Ry, Rz) with tag annotation."""

    @stim.main
    def test_rx_with_tag():
        gate.Rx(targets=(0,), angle=0.25, tag="rx_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_rx_with_tag)
    assert buf.getvalue().strip() == "I[R_X(theta=0.5*pi)][rx_tag] 0"

    @stim.main
    def test_ry_with_tag():
        gate.Ry(targets=(0,), angle=0.5, tag="ry_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_ry_with_tag)
    assert buf.getvalue().strip() == "I[R_Y(theta=1.0*pi)][ry_tag] 0"


def test_u3_gate_with_tag():
    """Test U3 gate with tag annotation."""

    @stim.main
    def test_u3_with_tag():
        gate.U3(targets=(0,), theta=0.25, phi=0.5, lam=0.125, tag="u3_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_u3_with_tag)
    assert (
        buf.getvalue().strip()
        == "I[U3(theta=0.5*pi, phi=1.0*pi, lambda=0.25*pi)][u3_tag] 0"
    )
