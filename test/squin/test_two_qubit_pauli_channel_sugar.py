import pytest

from bloqade import squin
from bloqade.squin.noise.stmts import PAULI_PRODUCT_ORDER


def test_two_qubit_pauli_channel_accepts_dict_in_kernel():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.two_qubit_pauli_channel({"XX": 0.1, "YY": 0.2, "ZZ": 0.15}, q[0], q[1])

    stmts = list(main.callable_region.walk())
    channel = next(
        stmt
        for stmt in stmts
        if isinstance(stmt, squin.noise.stmts.TwoQubitPauliChannel)
    )
    probabilities = list(channel.probabilities.owner.value.data)

    assert probabilities == [
        0.0,
        0.0,
        0.0,
        0.0,
        0.1,
        0.0,
        0.0,
        0.0,
        0.0,
        0.2,
        0.0,
        0.0,
        0.0,
        0.0,
        0.15,
    ]


def test_two_qubit_pauli_channel_preserves_list_form_in_kernel():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.two_qubit_pauli_channel(
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
            ],
            q[0],
            q[1],
        )

    stmts = list(main.callable_region.walk())
    channel = next(
        stmt
        for stmt in stmts
        if isinstance(stmt, squin.noise.stmts.TwoQubitPauliChannel)
    )

    assert list(channel.probabilities.owner.value.data) == [0.01] * len(
        PAULI_PRODUCT_ORDER
    )


def test_noise_two_qubit_pauli_channel_accepts_dict_in_kernel():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.noise.two_qubit_pauli_channel({"XX": 0.1}, q[0], q[1])

    stmts = list(main.callable_region.walk())
    channel = next(
        stmt
        for stmt in stmts
        if isinstance(stmt, squin.noise.stmts.TwoQubitPauliChannel)
    )

    assert list(channel.probabilities.owner.value.data)[4] == 0.1


def test_noise_two_qubit_pauli_channel_accepts_dict_with_qubit_ilists():
    @squin.kernel
    def main():
        q = squin.qalloc(4)
        squin.noise.two_qubit_pauli_channel({"XX": 0.1}, [q[0], q[1]], [q[2], q[3]])

    stmts = list(main.callable_region.walk())
    channel = next(
        stmt
        for stmt in stmts
        if isinstance(stmt, squin.noise.stmts.TwoQubitPauliChannel)
    )

    assert list(channel.probabilities.owner.value.data)[4] == 0.1
    assert channel.controls.owner is not channel.targets.owner
    assert type(channel.controls.owner).__name__ == "New"
    assert type(channel.targets.owner).__name__ == "New"
    assert len(channel.controls.owner.values) == 2
    assert len(channel.targets.owner.values) == 2


def test_two_qubit_pauli_channel_rejects_unknown_dict_keys():
    with pytest.raises(Exception, match="Invalid two-qubit Pauli product key"):

        @squin.kernel
        def main():
            q = squin.qalloc(2)
            squin.two_qubit_pauli_channel({"AA": 0.1}, q[0], q[1])
