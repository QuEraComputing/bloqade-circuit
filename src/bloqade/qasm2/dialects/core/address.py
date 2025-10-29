from kirin import interp
from kirin.analysis import const

from bloqade.analysis.address import (
    Address,
    AddressReg,
    ConstResult,
    UnknownQubit,
    AddressAnalysis,
)
from bloqade.analysis.address.lattice import UnknownReg

from .stmts import QRegGet, QRegNew
from ._dialect import dialect


@dialect.register(key="qubit.address")
class AddressMethodTable(interp.MethodTable):

    @interp.impl(QRegNew)
    def new(
        self,
        interp: AddressAnalysis,
        frame: interp.Frame[Address],
        stmt: QRegNew,
    ):
        n_qubits = frame.get(stmt.n_qubits)
        match n_qubits:
            case ConstResult(const.Value(int() as n)):
                addr = AddressReg(range(interp.next_address, interp.next_address + n))
                interp.next_address += n
                return (addr,)
            case _:
                return (UnknownReg(),)

    @interp.impl(QRegGet)
    def get(self, interp: AddressAnalysis, frame: interp.Frame[Address], stmt: QRegGet):
        addr = frame.get(stmt.reg)
        idx = frame.get(stmt.idx)

        typ, values = interp.unpack_iterable(addr)
        idx_value = interp.get_const_value(idx, int)

        if typ is not None and idx_value is not None:
            return (values[idx_value],)

        return (UnknownQubit(),)
