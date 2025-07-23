import ast
from dataclasses import dataclass

from kirin import types, lowering
from kirin.dialects import ilist

from bloqade.types import QubitType

from . import qubit


@dataclass(frozen=True)
class ApplyOrBroadcastCallLowering(lowering.FromPythonCall["qubit.Apply"]):
    """
    Custom lowering for Apply to deal with vararg qubits
    """

    def lower(
        self,
        stmt: type["qubit.Apply"] | type["qubit.Broadcast"],
        state: lowering.State,
        node: ast.Call,
    ):
        if len(node.args) + len(node.keywords) < 2:
            raise lowering.BuildError(
                "Apply / Broadcast requires at least one operator and one qubit argument!"
            )

        op, qubits = self.unpack_arguments(node)

        op_ssa = state.lower(op).expect_one()
        qubits_lowered = [state.lower(qbit).expect_one() for qbit in qubits]

        if stmt == qubit.Apply and any(
            [
                qbit_lowered.type.is_subseteq(ilist.IListType[QubitType, types.Any])
                for qbit_lowered in qubits_lowered
            ]
        ):
            raise lowering.BuildError(
                "The syntax `apply(op: Op, qubits: list[Qubit])` is no longer supported. Use `apply(op: Op, *qubits: Qubit)` instead!"
            )

        s = stmt(op_ssa, tuple(qubits_lowered))
        return state.current_frame.push(s)

    def unpack_arguments(self, node: ast.Call) -> tuple[ast.expr, list[ast.expr]]:
        if len(node.keywords) == 0:
            op, *qubits = node.args
            return op, qubits

        kwargs = {kw.arg: kw.value for kw in node.keywords}
        if len(kwargs) > 1 or "operator" not in kwargs:
            raise lowering.BuildError(f"Got unsupported keyword argument {kwargs}")

        op = kwargs["operator"]
        qubits = node.args

        return op, qubits
