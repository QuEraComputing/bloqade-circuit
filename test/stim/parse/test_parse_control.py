import pytest

from bloqade.stim.parse import loads

from .base import codegen


@pytest.mark.parametrize(
    "key,exp",
    [
        ("CX", "CX"),
        ("CY", "CY"),
        ("CZ", "CZ"),
    ],
)
def test_ctrl(key: str, exp: str):

    mt = loads(f"{key} rec[-1] 3 0 2")

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == f"{exp} rec[-1] 3 0 2"
