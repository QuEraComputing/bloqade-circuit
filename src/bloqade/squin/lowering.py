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
        if len(node.args) + len(node.keywords) < 2:
            raise lowering.BuildError(
                "Apply requires at least one operator and one qubit as arguments!"
            )

        op, qubits = self.unpack_arguments(node)

        op_ssa = state.lower(op).expect_one()
        qubits_lowered = [state.lower(qbit).expect_one() for qbit in qubits]

        s = stmt(op_ssa, tuple(qubits_lowered))
        return state.current_frame.push(s)

    def unpack_arguments(self, node: ast.Call) -> tuple[ast.expr, list[ast.expr]]:
        if len(node.keywords) == 0:
            op, *qubits = node.args
            return op, qubits

        kwargs = {kw.arg: kw.value for kw in node.keywords}
        if len(kwargs) > 2 or "qubits" not in kwargs:
            raise lowering.BuildError(f"Got unsupported keyword argument {kwargs}")

        qubits = kwargs["qubits"]
        if len(kwargs) == 1:
            if len(node.args) != 1:
                raise lowering.BuildError("Missing operator argument")
            op = node.args[0]
        else:
            try:
                op = kwargs["operator"]
            except KeyError:
                raise lowering.BuildError(f"Got unsupported keyword argument {kwargs}")

        if isinstance(qubits, ast.List):
            return op, qubits.elts

        return op, [qubits]


@dataclass(frozen=True)
class BroadcastCallLowering(lowering.FromPythonCall["qubit.Broadcast"]):
    """
    Custom lowering for broadcast vararg call.

    NOTE: we can re-use this to lower Apply too once we remove the deprecated syntax
    """

    def lower(
        self, stmt: type["qubit.Broadcast"], state: lowering.State, node: ast.Call
    ):
        if len(node.args) < 2:
            raise lowering.BuildError(
                "Broadcast requires at least one operator and one qubit list argument"
            )

        op, *qubit_lists = node.args

        op_lowered = state.lower(op).expect_one()
        qubits_lists_lowered = [
            state.lower(qubit_list).expect_one() for qubit_list in qubit_lists
        ]

        return state.current_frame.push(stmt(op_lowered, tuple(qubits_lists_lowered)))
