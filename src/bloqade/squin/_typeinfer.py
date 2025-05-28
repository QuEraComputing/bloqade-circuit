from kirin import types, interp
from kirin.analysis import TypeInference, const
from kirin.dialects import ilist

from bloqade import squin


@squin.qubit.dialect.register(key="typeinfer")
class TypeInfer(interp.MethodTable):
    @interp.impl(squin.qubit.New)
    def _call(self, interp: TypeInference, frame: interp.Frame, stmt: squin.qubit.New):
        # based on Xiu-zhe (Roger) Luo's get_const_value function

        if (hint := stmt.n_qubits.hints.get("const")) is None:
            return (ilist.IListType[squin.qubit.QubitType, types.Any],)

        if isinstance(hint, const.Value) and isinstance(hint.data, int):
            return (ilist.IListType[squin.qubit.QubitType, types.Literal(hint.data)],)

        return (ilist.IListType[squin.qubit.QubitType, types.Any],)
