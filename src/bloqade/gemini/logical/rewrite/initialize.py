from kirin import ir
from kirin.rewrite import abc as rewrite_abc

from bloqade.squin.gate.stmts import U3

from ..dialects.operations.stmts import Initialize


class __RewriteU3ToInitialize(rewrite_abc.RewriteRule):
    """Rewrite U3 gates to Initialize statements.

    Note:

    This rewrite is only valid in the context of logical qubits, where the U3 gate
    can be interpreted as initializing a qubit to an arbitrary state.

    The U3 gate with parameters (theta, phi, lam) is equivalent to initializing
    a qubit to the state defined by those angles.

    This rewrite also assumes there are no other U3 gates acting on the same qubits
    later in the circuit, as that would conflict with the initialization semantics.

    """

    def rewrite_Statement(self, node: ir.Statement) -> rewrite_abc.RewriteResult:
        if not isinstance(node, U3):
            return rewrite_abc.RewriteResult()

        node.replace_by(Initialize(*node.args))
        return rewrite_abc.RewriteResult(has_done_something=True)
