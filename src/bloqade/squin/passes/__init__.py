"""Compiler passes for the squin dialect."""

from .parallelize import ParallelizeLayer as ParallelizeLayer
from .layer_optimize import LayerOptimize as LayerOptimize
from .qasm2_to_squin import QASM2ToSquin as QASM2ToSquin
from .qasm3_to_squin import QASM3ToSquin as QASM3ToSquin
from .clifford_normalize import CliffordNormalize as CliffordNormalize
