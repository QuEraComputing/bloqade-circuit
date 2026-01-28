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


# =============================================================================
# Collapse dialect tag tests
# =============================================================================


def test_measurement_with_tag():
    """Test measurement gates with tag annotation."""

    @stim.main
    def test_mz_with_tag():
        stim.mz(targets=(0, 1), p=0.01, tag="mz_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_mz_with_tag)
    assert buf.getvalue().strip() == "MZ[mz_tag](0.01000000) 0 1"


def test_reset_with_tag():
    """Test reset gates with tag annotation."""

    @stim.main
    def test_rz_with_tag():
        stim.rz(targets=(0, 1), tag="rz_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_rz_with_tag)
    assert buf.getvalue().strip() == "RZ[rz_tag] 0 1"


def test_ppmeasurement_with_tag():
    """Test Pauli-product measurement with tag annotation."""

    @stim.main
    def test_mpp_with_tag():
        stim.mpp(
            targets=(
                stim.pauli_string(
                    string=("X", "Z"),
                    flipped=(False, False),
                    targets=(0, 1),
                ),
            ),
            p=0.01,
            tag="mpp_tag",
        )

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_mpp_with_tag)
    assert buf.getvalue().strip() == "MPP[mpp_tag](0.01000000) X0*Z1"


# =============================================================================
# Noise dialect tag tests
# =============================================================================


def test_depolarize_with_tag():
    """Test depolarize noise with tag annotation."""

    @stim.main
    def test_depolarize1_with_tag():
        stim.depolarize1(p=0.01, targets=(0, 1), tag="dep1_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_depolarize1_with_tag)
    assert buf.getvalue().strip() == "DEPOLARIZE1[dep1_tag](0.01000000) 0 1"


def test_pauli_channel_with_tag():
    """Test Pauli channel noise with tag annotation."""

    @stim.main
    def test_pauli_channel1_with_tag():
        stim.pauli_channel1(px=0.01, py=0.02, pz=0.03, targets=(0,), tag="pc1_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_pauli_channel1_with_tag)
    assert (
        buf.getvalue().strip()
        == "PAULI_CHANNEL_1[pc1_tag](0.01000000, 0.02000000, 0.03000000) 0"
    )


# =============================================================================
# Auxiliary dialect tag tests
# =============================================================================


def test_tick_with_tag():
    """Test TICK instruction with tag annotation."""

    @stim.main
    def test_tick_with_tag():
        stim.tick(tag="tick_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_tick_with_tag)
    assert buf.getvalue().strip() == "TICK[tick_tag]"


def test_detector_with_tag():
    """Test DETECTOR instruction with tag annotation."""

    @stim.main
    def test_detector_with_tag():
        stim.mz(targets=(0,))
        stim.detector(coord=(1.0, 2.0), targets=(stim.rec(-1),), tag="det_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_detector_with_tag)
    output = buf.getvalue().strip().split("\n")
    assert output[1] == "DETECTOR[det_tag](1.00000000, 2.00000000) rec[-1]"


def test_observable_include_with_tag():
    """Test OBSERVABLE_INCLUDE instruction with tag annotation."""

    @stim.main
    def test_obs_include_with_tag():
        stim.mz(targets=(0,))
        stim.observable_include(idx=0, targets=(stim.rec(-1),), tag="obs_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_obs_include_with_tag)
    output = buf.getvalue().strip().split("\n")
    assert output[1] == "OBSERVABLE_INCLUDE[obs_tag](0) rec[-1]"


def test_qubit_coordinates_with_tag():
    """Test QUBIT_COORDS instruction with tag annotation."""

    @stim.main
    def test_qubit_coords_with_tag():
        stim.qubit_coordinates(coord=(1.0, 2.0, 3.0), target=0, tag="qc_tag")

    buf = io.StringIO()
    stim_emit = EmitStimMain(dialects=stim.main, io=buf)
    stim_emit.run(test_qubit_coords_with_tag)
    assert buf.getvalue().strip() == "QUBIT_COORDS[qc_tag](1.00000000, 2.00000000, 3.00000000) 0"
