import pytest

from bloqade.stim.parse import loads

from .base import codegen


@pytest.mark.parametrize(
    "key,exp",
    [
        ("X", "X"),
        ("Y", "Y"),
        ("Z", "Z"),
        ("H", "H"),
        ("S", "S"),
        ("S_DAG", "S_DAG"),
        ("I", "I"),
        ("SQRT_X", "SQRT_X"),
        ("SQRT_Y", "SQRT_Y"),
        ("SQRT_Z", "S"),
        ("SQRT_X_DAG", "SQRT_X_DAG"),
        ("SQRT_Y_DAG", "SQRT_Y_DAG"),
        ("SQRT_Z_DAG", "S_DAG"),
    ],
)
def test_1q(key: str, exp: str):

    mt = loads(f"{key} 5 0 1 2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    print(out)
    assert out.strip() == f"{exp} 5 0 1 2"


def test_swap():
    mt = loads("SWAP 5 0 1 2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "SWAP 5 0 1 2"
