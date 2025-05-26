from kirin import types, interp
from kirin.analysis import TypeInference, const
from kirin.dialects import ilist

from bloqade import squin


@squin.qubit.dialect.register(key="typeinfer")
class TypeInfer(interp.MethodTable):
    @interp.impl(squin.qubit.New)
    def _call(self, interp: TypeInference, frame: interp.Frame, stmt: squin.qubit.New):
        # based on Xiu-zhe (Roger) Luo's get_const_value function

        if "const" not in stmt.n_qubits.hints:
            return (ilist.IListType[squin.qubit.QubitType, types.Any],)

        if isinstance(hint := stmt.n_qubits.hints["const"], const.Value):
            data = hint.data
            if isinstance(data, int):
                return (ilist.IListType[squin.qubit.QubitType, types.Literal(data)],)

        return (ilist.IListType[squin.qubit.QubitType, types.Any],)
