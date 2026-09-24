"""This package holds the analysis that states which root each value refers to.

`ReferenceAnalysis` holds the rules for kirin's own dialects. A subclass adds the
roots of one kind of tracked state, such as squin qubits or jeff wires.
"""

from . import impls as impls
from .lattice import (
    CARRIED as CARRIED,
    UNTRACKED as UNTRACKED,
    Ref as Ref,
    Slot as Slot,
    Items as Items,
    Whole as Whole,
    Bottom as Bottom,
    Unknown as Unknown,
    Register as Register,
    Returned as Returned,
    Positions as Positions,
    Untracked as Untracked,
)
from .analysis import (
    KEY as KEY,
    ReferenceAnalysis as ReferenceAnalysis,
)
