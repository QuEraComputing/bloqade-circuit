"""Count matching IR statements by walking reachable kernels.

``scf.For`` bodies are counted once; ``scf.IfElse`` visits both branches.
"""

from . import impls as impls
from .analysis import CountStatementAnalysis as CountStatementAnalysis
