"""Hold the squin wire dialect, which makes quantum state flow explicit.

A wire is one qubit at one point in the program, and it has exactly one use. Each
statement consumes its input wires and returns new wires. The conversion passes live in `bloqade.squin.passes`.
"""

from . import typeinfer as typeinfer
from .group import (
    kernel as kernel,
    is_wire as is_wire,
    wire_group as wire_group,
    reference_group as reference_group,
)
from .kinds import GateKind as GateKind, NoiseKind as NoiseKind
from .stmts import (
    Free as Free,
    Gate as Gate,
    Alloc as Alloc,
    Noise as Noise,
    Reset as Reset,
    Borrow as Borrow,
    Length as Length,
    Measure as Measure,
    Release as Release,
    Operation as Operation,
    FreeRegister as FreeRegister,
    RegisterGate as RegisterGate,
    AllocRegister as AllocRegister,
    RegisterNoise as RegisterNoise,
    RegisterReset as RegisterReset,
    RegisterMeasure as RegisterMeasure,
    RegisterOperation as RegisterOperation,
)
from .types import (
    Wire as Wire,
    Register as Register,
    WireType as WireType,
    RegisterType as RegisterType,
    is_linear as is_linear,
)
from .errors import WireConversionError as WireConversionError
from .traits import (
    Threads as Threads,
    ThreadsPairs as ThreadsPairs,
    ReferenceForm as ReferenceForm,
    ThreadsInOrder as ThreadsInOrder,
)
from ._dialect import dialect as dialect
