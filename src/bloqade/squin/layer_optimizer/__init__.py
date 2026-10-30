"""Layer-optimization helpers for Clifford circuits.

Pure cirq leaves used by ``LayerOptimize``: ``schedule`` (per-CZ-gap extraction
and frame materialization), ``simplify`` (combine diagonals through CZ), ``cost``
(fast layer-count predictor), and ``search`` (bounded-uphill frame search).
"""
