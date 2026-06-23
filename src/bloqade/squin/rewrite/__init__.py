"""Rewrite rules for the squin dialect."""

from .parallelize import SquinBatchBroadcastsRule as SquinBatchBroadcastsRule
from .U3_to_clifford import SquinU3ToClifford as SquinU3ToClifford
