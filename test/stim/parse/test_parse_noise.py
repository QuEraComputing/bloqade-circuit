import pytest

from bloqade.stim.parse import loads

from .base import codegen


@pytest.mark.parametrize(
    "key,exp",
    [
        ("DEPOLARIZE1", "DEPOLARIZE1"),
        ("DEPOLARIZE2", "DEPOLARIZE2"),
        ("X_ERROR", "X_ERROR"),
        ("Y_ERROR", "Y_ERROR"),
        ("Z_ERROR", "Z_ERROR"),
    ],
)
def test_1p(key: str, exp: str):

    mt = loads(f"{key}(0.2) 5 0 1 2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    print(out)
    assert out.strip() == f"{exp}(0.20000000) 5 0 1 2"


def test_pauli_ch1():
    mt = loads("PAULI_CHANNEL_1(0.2, 0.3, 0.4) 5 0 1 2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "PAULI_CHANNEL_1(0.20000000, 0.30000000, 0.40000000) 5 0 1 2"


def test_pauli_ch2():
    x = tuple(0.005 * i for i in range(15))

    x_str = ", ".join([f"{i:.3f}" for i in x])
    print(f"PAULI_CHANNEL_2({x_str}) 5 0 1 2")
    mt = loads(f"PAULI_CHANNEL_2{x} 5 0 1 2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    x_exp = ", ".join([f"{i:.8f}" for i in x])
    assert out.strip() == f"PAULI_CHANNEL_2({x_exp}) 5 0 1 2"
