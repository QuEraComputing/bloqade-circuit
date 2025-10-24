from kirin import interp
from kirin.analysis import ForwardFrame

from bloqade.analysis.address.lattice import (
    Address,
    AddressQubit,
)
from bloqade.analysis.address.analysis import AddressAnalysis

from .. import stmts
from .._dialect import dialect

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


@dialect.register(key="qubit.address")
class SquinQubitMethodTable(interp.MethodTable):

    @interp.impl(stmts.New)
    def new_qubit(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: stmts.New,
    ):
        addr = AddressQubit(interp_.next_address)
        interp_.next_address += 1
        return (addr,)
