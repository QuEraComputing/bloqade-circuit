"""Guard against import-cycle regressions in the squin pass package.

These imports must succeed in a *fresh* interpreter where nothing else has been
imported first — otherwise a latent cycle (e.g. ``squin.analysis.schedule`` <->
``qasm2``) only shows up for end users, not in the test suite (which loads many
modules before any single one and so masks the ordering bug).
"""

import sys
import subprocess

import pytest

_COLD_IMPORTS = [
    "from bloqade.squin.passes import LayerOptimize, ParallelizeLayer, CliffordNormalize",
    "import bloqade.squin.layer_optimizer.schedule",
    "import bloqade.squin.passes.clifford_normalize",
]


@pytest.mark.parametrize("stmt", _COLD_IMPORTS)
def test_cold_import_has_no_cycle(stmt: str):
    result = subprocess.run(
        [sys.executable, "-c", stmt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert (
        result.returncode == 0
    ), f"cold import failed: {stmt}\n{result.stdout}\n{result.stderr}"
