import ast
from dataclasses import dataclass

from kirin import lowering

from . import stmts


@dataclass(frozen=True)
class OperatorWithArgLowering(lowering.FromPythonCall):
    def lower(
        self, stmt: type["stmts.ConstantOp"], state: lowering.State, node: ast.Call
    ):
        op = state.current_frame.push(stmt())

        if len(node.args) + len(node.keywords) == 0:
            return op

        if len(node.keywords) != 0:
            raise NotImplementedError(
                "Named arguments in operator call not yet supported"
            )

        # NOTE: avoid circular import issues
        from bloqade.squin.qubit import ApplyAny

        qubits = [state.lower(qbit).expect_one() for qbit in node.args]
        return state.current_frame.push(
            ApplyAny(operator=op.result, qubits=tuple(qubits))
        )
