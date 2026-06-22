import sys
import subprocess
from pathlib import Path

import tomlkit


def _assert_import_succeeds_without_qpsolvers(module_name: str):
    code = f"""
import importlib
import sys


class BlockQPSolversImport:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "qpsolvers" or fullname.startswith("qpsolvers."):
            raise ImportError("blocked qpsolvers import")
        return None


sys.meta_path.insert(0, BlockQPSolversImport())
importlib.import_module({module_name!r})
"""

    subprocess.run([sys.executable, "-c", code], check=True)


def test_cirq_utils_import_without_qpsolvers():
    """Import Cirq utilities without requiring qpsolvers."""
    _assert_import_succeeds_without_qpsolvers("bloqade.cirq_utils")


def test_gemini_noise_model_import_without_qpsolvers():
    """Import the Gemini noise model without requiring qpsolvers."""
    _assert_import_succeeds_without_qpsolvers("bloqade.cirq_utils.noise.model")


def test_qpsolvers_is_not_part_of_base_cirq_extra():
    """Keep qpsolvers in the parallelization extra, not the base Cirq extra."""
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    optional_dependencies = tomlkit.loads(pyproject.read_text())["project"][
        "optional-dependencies"
    ]

    assert not any("qpsolvers" in dep for dep in optional_dependencies["cirq"])
    assert any("qpsolvers" in dep for dep in optional_dependencies["cirq-parallelize"])
