from .callgraph import (
    CallGraphPass as CallGraphPass,
    ReplaceMethods as ReplaceMethods,
    UpdateDialectsOnCallGraph as UpdateDialectsOnCallGraph,
)
from .aggressive_unroll import AggressiveUnroll as AggressiveUnroll
from .canonicalize_ilist import CanonicalizeIList as CanonicalizeIList
from .remove_empty_args import RemoveEmptyArgGates as RemoveEmptyArgGates
