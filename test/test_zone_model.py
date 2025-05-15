import math

from bloqade.noise import native


def test_zone_model_deconflict():

    noise_model = native.TwoRowZoneModel()

    result = noise_model.deconflict([0, 4, 2, 1], [3, 5, 6, 7])
    assert result == [((0, 1), (3, 7)), ((2,), (6,)), ((4,), (5,))]


def test_coeff():

    noise_model = native.TwoRowZoneModel()
    result = noise_model.parallel_cz_errors([0, 4, 2, 1], [3, 5, 6, 7], [])
    print(result)
    qubit_result = {}

    for p, qubits in result.items():
        for qubit in qubits:
            qubit_result[qubit] = p

    expected_p = (
        0.0026594422101715335,
        0.0026594422101715335,
        0.0062921137981472395,
        0.0,
    )

    expected_qubit_result = {
        0: expected_p,
        1: expected_p,
        2: expected_p,
        3: expected_p,
        4: expected_p,
        5: expected_p,
        6: expected_p,
        7: expected_p,
    }

    for q, p in qubit_result.items():
        assert math.isclose(p[0], expected_qubit_result[q][0])
        assert math.isclose(p[1], expected_qubit_result[q][1])
        assert math.isclose(p[2], expected_qubit_result[q][2])
        assert math.isclose(p[3], expected_qubit_result[q][3])
