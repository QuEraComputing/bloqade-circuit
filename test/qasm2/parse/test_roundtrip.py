import os
import pathlib

import pytest
from lark.exceptions import UnexpectedToken

from bloqade.qasm2.parse import loads, spprint, loadfile


def roundtrip(file, dirname):
    ast1 = loadfile(os.path.join(os.path.dirname(__file__), dirname, file))
    ast2 = loads(spprint(ast1))
    return ast1 == ast2


def test_roundtrip():
    dirname = "programs"
    path = pathlib.Path(__file__).parent / dirname
    for file in path.glob("*.qasm"):
        assert roundtrip(file.name, dirname), f"Failed roundtrip for {file}"


def test_invalids():
    dirname = "invalid_programs"
    path = pathlib.Path(__file__).parent / dirname
    for file in path.glob("*.qasm"):
        with pytest.raises(UnexpectedToken):
            roundtrip(file.name, dirname)
