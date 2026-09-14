"""Accumulate weighted counts while walking reachable IR.

Callable bodies and structured control flow are traversed statically: ``scf.For``
bodies are visited once and ``scf.IfElse`` visits both branches.
"""

from . import impls as impls
from .analysis import CountStatementAnalysis as CountStatementAnalysis
