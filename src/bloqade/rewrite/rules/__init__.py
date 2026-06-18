"""Rewrite rules for bloqade IR transformations."""

from .split_ifs import LiftThenBody as LiftThenBody, SplitIfStmts as SplitIfStmts
from .remove_empty_arg_gates import RemoveEmptyArgOps as RemoveEmptyArgOps
