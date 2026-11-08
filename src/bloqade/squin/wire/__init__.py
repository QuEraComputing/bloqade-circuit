"""Compose the squin wire dialects, which make quantum state flow explicit.

A wire is one qubit at one point in the program, and it has exactly one use. Each
statement consumes its input wires and returns new wires. The conversion passes live in `bloqade.squin.passes`.
"""

from . import gate as gate, noise as noise, state as state, typeinfer as typeinfer
from .group import (
    WIRE_DIALECTS as WIRE_DIALECTS,
    kernel as kernel,
    is_wire as is_wire,
    wire_group as wire_group,
    reference_group as reference_group,
)
from .kinds import GateKind as GateKind, NoiseKind as NoiseKind
from .stmts import (
    Put as Put,
    Free as Free,
    Gate as Gate,
    Take as Take,
    Alloc as Alloc,
    Noise as Noise,
    Reset as Reset,
    Borrow as Borrow,
    Length as Length,
    Measure as Measure,
    Release as Release,
    PutSlice as PutSlice,
    Operation as Operation,
    TakeSlice as TakeSlice,
    FreeRegister as FreeRegister,
    JoinRegister as JoinRegister,
    PackRegister as PackRegister,
    RegisterGate as RegisterGate,
    AllocRegister as AllocRegister,
    RegisterNoise as RegisterNoise,
    RegisterReset as RegisterReset,
    SplitRegister as SplitRegister,
    CorrelatedLoss as CorrelatedLoss,
    DiscardRegister as DiscardRegister,
    RegisterMeasure as RegisterMeasure,
    RegisterOperation as RegisterOperation,
)
from .types import (
    Wire as Wire,
    Register as Register,
    WireType as WireType,
    RegisterType as RegisterType,
    is_linear as is_linear,
    register_type as register_type,
    register_length as register_length,
)
from .errors import WireConversionError as WireConversionError
from .traits import (
    Threads as Threads,
    ReferenceForm as ReferenceForm,
)
