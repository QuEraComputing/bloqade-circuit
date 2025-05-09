from kirin import types, interp
from kirin.analysis import TypeInference
from kirin.dialects import py, ilist

from bloqade.qasm2.types import CRegType, QRegType, QubitType

from .stmts import QRegNew
from ._dialect import dialect


@dialect.register(key="typeinfer")
class TypeInfer(interp.MethodTable):

    @interp.impl(QRegNew)
    def range(
        self,
        interp_: TypeInference,
        frame: interp.Frame[types.TypeAttribute],
        stmt: QRegNew,
    ):
        n_qubits = interp_.maybe_const(stmt.n_qubits, int)
        if n_qubits:
            return (ilist.IListType[QubitType, types.Literal(n_qubits)],)
        return (ilist.IListType[QubitType, types.Any],)

    @interp.impl(py.indexing.GetItem, QRegType, types.Int)
    def getitem_qreg(
        self, infer: TypeInference, frame: interp.Frame, node: py.indexing.GetItem
    ):
        return (QubitType,)

    @interp.impl(py.indexing.GetItem, CRegType, types.Int)
    def getitem_creg(
        self, infer: TypeInference, frame: interp.Frame, node: py.indexing.GetItem
    ):
        return (QubitType,)
