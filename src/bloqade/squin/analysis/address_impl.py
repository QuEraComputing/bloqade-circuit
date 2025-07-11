from kirin import interp
from kirin.analysis import ForwardFrame

from bloqade.analysis.address.lattice import (
    Address,
    AddressReg,
    AddressWire,
    AddressQubit,
)
from bloqade.analysis.address.analysis import AddressAnalysis

from .. import wire, qubit

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


@wire.dialect.register(key="qubit.address")
class SquinWireMethodTable(interp.MethodTable):

    @interp.impl(wire.Unwrap)
    def unwrap(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: wire.Unwrap,
    ):

        origin_qubit = frame.get(stmt.qubit)

        if isinstance(origin_qubit, AddressQubit):
            return (AddressWire(origin_qubit=origin_qubit),)
        else:
            return (Address.top(),)

    @interp.impl(wire.Apply)
    def apply(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: wire.Apply,
    ):
        return frame.get_values(stmt.inputs)


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
