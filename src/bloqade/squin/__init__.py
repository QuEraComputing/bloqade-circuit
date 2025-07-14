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

try:
    # NOTE: make sure optional cirq dependency is installed
    import cirq as cirq_package  # noqa: F401
except ImportError:
    pass
else:
    from . import cirq as cirq
    from .cirq import load_circuit as load_circuit
