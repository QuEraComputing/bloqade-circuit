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
        if len(node.keywords) > 0:
            kwargs = {kw.arg: kw.value for kw in node.keywords}
            raise lowering.BuildError(f"Got unsupported keyword arguments {kwargs}")

        if len(node.args) < 2:
            raise lowering.BuildError(
                "Apply / Broadcast requires at least one operator and one qubit argument!"
            )

        op, *qubits = node.args

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
