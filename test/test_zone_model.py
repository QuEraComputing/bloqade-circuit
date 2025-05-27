from bloqade.qasm2 import noise as noise


def test_zone_model_deconflict():

    noise_model = noise.TwoRowZoneModel()

    result = noise_model.deconflict([0, 4, 2, 1], [3, 5, 6, 7])
    assert result == [((0, 1), (3, 7)), ((2,), (6,)), ((4,), (5,))]


def test_coeff():

    noise_model = noise.TwoRowZoneModel(
        mover_px=0.0,
        mover_py=0.0,
        mover_pz=0.0,
        sitter_px=0.0,
        sitter_py=0.0,
        sitter_pz=0.0,
    )
    result = noise_model.parallel_cz_errors([0], [1], [])

    expected_p = (0.0, 0.0, 0.0, 0.0)

    qubit_result = {}

    for p, qubits in result.items():
        for qubit in qubits:
            qubit_result[qubit] = p

    expected_qubit_result = {
        0: expected_p,
        1: expected_p,
    }
    assert qubit_result == expected_qubit_result
