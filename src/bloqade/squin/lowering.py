import ast
from dataclasses import dataclass

from kirin import lowering

from . import qubit


@dataclass(frozen=True)
class ApplyAnyCallLowering(lowering.FromPythonCall["qubit.ApplyAny"]):
    """
    Custom lowering for ApplyAny that collects vararg qubits into a single tuple argument
    """

    def lower(
        self, stmt: type["qubit.ApplyAny"], state: lowering.State, node: ast.Call
    ):
        if len(node.args) < 2:
            raise lowering.BuildError(
                "Apply requires at least one operator and one qubit as arguments!"
            )
        op, *qubits = node.args
        op_ssa = state.lower(op).expect_one()
        qubits_lowered = [state.lower(qbit).expect_one() for qbit in qubits]

        s = stmt(op_ssa, tuple(qubits_lowered))
        return state.current_frame.push(s)
