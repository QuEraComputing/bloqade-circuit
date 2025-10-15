from kirin import interp
from kirin.analysis import ForwardFrame

from bloqade.analysis.address.lattice import (
    Address,
    AddressReg,
)
from bloqade.analysis.address.analysis import AddressAnalysis

from .. import qubit

# Address lattice elements we can work with:
## NotQubit (bottom), AnyAddress (top)

## AddressTuple -> data: tuple[Address, ...]
### Recursive type, could contain itself or other variants
### This pops up in cases where you can have an IList/Tuple
### That contains elements that could be other Address types

## AddressReg -> data: Sequence[int]
### specific to creation of a register of qubits

## AddressQubit -> data: int
### Base qubit address type


@qubit.dialect.register(key="qubit.address")
class SquinQubitMethodTable(interp.MethodTable):

    # This can be treated like a QRegNew impl
    @interp.impl(qubit.New)
    def new(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: qubit.New,
    ):
        n_qubits = interp_.get_const_value(int, stmt.n_qubits)
        addr = AddressReg(range(interp_.next_address, interp_.next_address + n_qubits))
        interp_.next_address += n_qubits
        return (addr,)
