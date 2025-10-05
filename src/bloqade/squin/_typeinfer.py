from kirin import types, interp
from kirin.analysis import TypeInference, const
from kirin.dialects import ilist

from bloqade.squin import qubit


@qubit.dialect.register(key="typeinfer")
class TypeInfer(interp.MethodTable):
    @interp.impl(qubit.stmts.New)
    def _call(self, interp: TypeInference, frame: interp.Frame, stmt: qubit.stmts.New):
        # based on Xiu-zhe (Roger) Luo's get_const_value function

        if (hint := stmt.n_qubits.hints.get("const")) is None:
            return (ilist.IListType[qubit.stmts.QubitType, types.Any],)

        if isinstance(hint, const.Value) and isinstance(hint.data, int):
            return (ilist.IListType[qubit.stmts.QubitType, types.Literal(hint.data)],)

        return (ilist.IListType[qubit.stmts.QubitType, types.Any],)
