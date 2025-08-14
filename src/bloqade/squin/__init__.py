from . import (
    op as op,
    wire as wire,
    noise as noise,
    qubit as qubit,
    analysis as analysis,
    lowering as lowering,
    _typeinfer as _typeinfer,
)
from .groups import wired as wired, kernel as kernel

# NOTE: it's important to keep these imports here since they import squin.kernel
# we skip isort here
from . import parallel as parallel  # isort: skip
from .stdlib import gate as gate, channel as channel  # isort: skip

try:
    # NOTE: make sure optional cirq dependency is installed
    import cirq as cirq_package  # noqa: F401
except ImportError:
    pass
else:
    from . import cirq as cirq
    from .cirq import load_circuit as load_circuit
