"""Accumulate weighted leaf-statement counts while walking reachable IR.

Callable bodies and structured control flow are traversed statically: ``scf.For``
bodies are visited once and ``scf.IfElse`` visits both branches. Call,
control-flow, and higher-order traversal operations are not themselves counted.
"""

from . import impls as impls
from .analysis import CountStatementAnalysis as CountStatementAnalysis
