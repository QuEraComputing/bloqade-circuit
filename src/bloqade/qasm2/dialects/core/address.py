from kirin import interp

from bloqade.analysis.address import (
    Address,
    NotQubit,
    AddressReg,
    AddressQubit,
    AddressAnalysis,
)

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
        n_qubits = interp.expect_const(stmt.n_qubits, int)
        addr = AddressReg(range(interp.next_address, interp.next_address + n_qubits))
        interp.next_address += n_qubits
        return (addr,)

    @interp.impl(QRegGet)
    def get(self, interp: AddressAnalysis, frame: interp.Frame[Address], stmt: QRegGet):
        addr = frame.get(stmt.reg)
        pos = interp.expect_const(stmt.idx, int)
        if isinstance(addr, AddressReg):
            global_idx = addr.data[pos]
            return (AddressQubit(global_idx),)
        else:  # this is not reachable
            return (NotQubit(),)
