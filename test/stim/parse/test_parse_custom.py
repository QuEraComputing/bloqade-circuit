from bloqade.stim.parse import loads
from bloqade.stim.dialects import noise

from .base import codegen


def test_parse_trivial():
    mt = loads(
        "I_ERROR[TRIV_ERROR](0.2, 0.3) 5 0 1 2",
        nonstim_noise_ops={"TRIV_ERROR": noise.TrivialError},
    )

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "I_ERROR[TRIV_ERROR](0.20000000, 0.30000000) 5 0 1 2"


def test_parse_trivial_correlated():
    mt = loads(
        "I_ERROR[TRIV_CORR_ERROR:3](0.2, 0.3) 5 0 1 2",
        nonstim_noise_ops={"TRIV_CORR_ERROR": noise.TrivialCorrelatedError},
    )

    mt.print()

    # test roundtrip
    out = codegen(mt)
    assert out.strip() == "I_ERROR[TRIV_CORR_ERROR:3](0.20000000, 0.30000000) 5 0 1 2"
