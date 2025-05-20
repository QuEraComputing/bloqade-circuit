import ast
from dataclasses import dataclass

from kirin import lowering
from kirin.dialects import ilist

from . import qubit


@dataclass(frozen=True)
class ApplyCallLowering(lowering.FromPythonCall["qubit.Apply"]):
    """
    Custom lowering for apply, that turns syntax sugar such as
    apply(op, q0, q1, ...) into the required apply(op, ilist.IList[q0, q1, ...])
    """

    def lower(self, stmt: type["qubit.Apply"], state: lowering.State, node: ast.Call):
        if len(node.args) < 2:
            raise lowering.BuildError(
                "Apply requires at least one operator and one qubit as arguments!"
            )
        op, *qubits = node.args
        op_ssa = state.lower(op).expect_one()

        qubits_lowered = [state.lower(qbit).expect_one() for qbit in qubits]

        if len(qubits_lowered) == 1 and qubits_lowered[0].type.is_subseteq(
            ilist.IListType
        ):
            # NOTE: this is a call with just a single argument that is already a list
            s = stmt(operator=op_ssa, qubits=qubits_lowered[0])
            result = state.current_frame.push(s)
        else:
            # NOTE: multiple values in the call or it's not a list (single qubit)
            # let's collect them to an ilist
            qubits_ilist = ilist.New(values=tuple(qubits_lowered))
            s = stmt(operator=op_ssa, qubits=qubits_ilist.result)
            result = state.current_frame.push(s)
            qubits_ilist.insert_before(s)

        return result
